terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }

  # Uncomment and configure for remote state storage
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "weather-app/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Serverless Weather Notification System"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "Bancha Setthanan"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Random string for unique resource names
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

###########################################
# VARIABLES
###########################################

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "weather_api_key" {
  description = "OpenWeatherMap API key"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "serverless-weather-notification-system"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 300
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

###########################################
# LOCALS
###########################################

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
  }

  lambda_functions = {
    weather_fetcher = {
      name        = "${local.name_prefix}-weather-fetcher"
      handler     = "lambda_function.lambda_handler"
      runtime     = "python3.13"
      timeout     = var.lambda_timeout
      memory_size = var.lambda_memory_size
    }
    weather_processor = {
      name        = "${local.name_prefix}-weather-processor"
      handler     = "lambda_function.lambda_handler"
      runtime     = "python3.13"
      timeout     = 60
      memory_size = 512
    }
    authorizer = {
      name        = "${local.name_prefix}-authorizer"
      handler     = "lambda_function.lambda_handler"
      runtime     = "python3.13"
      timeout     = 10
      memory_size = 128
    }
  }
}

###########################################
# S3 BUCKET FOR WEATHER DATA
###########################################

resource "aws_s3_bucket" "weather_bucket" {
  bucket = "${local.name_prefix}-data-${random_string.suffix.result}"

  tags = merge(local.common_tags, {
    Name = "Weather Data Bucket"
    Type = "Storage"
  })
}

resource "aws_s3_bucket_versioning" "weather_bucket_versioning" {
  bucket = aws_s3_bucket.weather_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "weather_bucket_encryption" {
  bucket = aws_s3_bucket.weather_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "weather_bucket_lifecycle" {
  bucket = aws_s3_bucket.weather_bucket.id

  rule {
    id     = "weather_data_lifecycle"
    status = "Enabled"

    # Transition to IA after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after 90 days
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Delete after 365 days (adjust as needed)
    expiration {
      days = 365
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_public_access_block" "weather_bucket_pab" {
  bucket = aws_s3_bucket.weather_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###########################################
# SECRETS MANAGER
###########################################

resource "aws_secretsmanager_secret" "weather_api_key" {
  name        = "${local.name_prefix}-api-key"
  description = "Weather API key for external weather service"

  tags = merge(local.common_tags, {
    Name = "Weather API Key"
    Type = "Secret"
  })
}

resource "aws_secretsmanager_secret_version" "weather_api_key" {
  secret_id     = aws_secretsmanager_secret.weather_api_key.id
  secret_string = var.weather_api_key
}

###########################################
# SQS QUEUE
###########################################

resource "aws_sqs_queue" "weather_queue" {
  name                       = "${local.name_prefix}-processing-queue"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600 # 14 days
  receive_wait_time_seconds  = 10      # Long polling
  visibility_timeout_seconds = var.sqs_visibility_timeout

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.weather_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name = "Weather Processing Queue"
    Type = "Queue"
  })
}

# Dead Letter Queue
resource "aws_sqs_queue" "weather_dlq" {
  name                      = "${local.name_prefix}-dlq"
  message_retention_seconds = 1209600

  tags = merge(local.common_tags, {
    Name = "Weather DLQ"
    Type = "Queue"
  })
}

###########################################
# SNS TOPIC
###########################################

resource "aws_sns_topic" "weather_notifications" {
  name = "${local.name_prefix}-notifications"

  tags = merge(local.common_tags, {
    Name = "Weather Notifications"
    Type = "Notification"
  })
}

# Optional: Add email subscription
# resource "aws_sns_topic_subscription" "weather_email" {
#   topic_arn = aws_sns_topic.weather_notifications.arn
#   protocol  = "email"
#   endpoint  = "your-email@example.com"
# }

###########################################
# IAM ROLES AND POLICIES
###########################################

# Lambda execution role
resource "aws_iam_role" "lambda_execution_role" {
  name = "${local.name_prefix}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Lambda execution policy
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "${local.name_prefix}-lambda-execution-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.weather_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.weather_bucket.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.weather_queue.arn,
          aws_sqs_queue.weather_dlq.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.weather_notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.weather_api_key.arn
      }
    ]
  })
}

# API Gateway invocation role for authorizer
resource "aws_iam_role" "api_gateway_invocation_role" {
  name = "${local.name_prefix}-api-gateway-invocation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "api_gateway_invocation_policy" {
  name = "${local.name_prefix}-api-gateway-invocation-policy"
  role = aws_iam_role.api_gateway_invocation_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "lambda:InvokeFunction"
        Effect   = "Allow"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-*"
      }
    ]
  })
}

###########################################
# CLOUDWATCH LOG GROUPS
###########################################

resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = local.lambda_functions

  name              = "/aws/lambda/${each.value.name}"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Name = "${each.key} Log Group"
    Type = "Logs"
  })
}

###########################################
# LAMBDA FUNCTIONS
###########################################

# Placeholder Lambda function - will be updated by CI/CD
resource "aws_lambda_function" "weather_functions" {
  for_each = local.lambda_functions

  filename      = "${path.module}/placeholder.zip"
  function_name = each.value.name
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = each.value.handler
  runtime       = each.value.runtime
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size

  environment {
    variables = merge(
      {
        ENVIRONMENT     = var.environment
        PROJECT_NAME    = var.project_name
        AWS_REGION_NAME = data.aws_region.current.name
      },
      each.key == "weather_fetcher" ? {
        WEATHER_API_SECRET_NAME = aws_secretsmanager_secret.weather_api_key.name
        SQS_QUEUE_URL           = aws_sqs_queue.weather_queue.id
        S3_BUCKET_NAME          = aws_s3_bucket.weather_bucket.bucket
      } : {},
      each.key == "weather_processor" ? {
        S3_BUCKET_NAME = aws_s3_bucket.weather_bucket.bucket
        SNS_TOPIC_ARN  = aws_sns_topic.weather_notifications.arn
      } : {}
    )
  }

  depends_on = [
    aws_iam_role_policy.lambda_execution_policy,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = merge(local.common_tags, {
    Name = each.value.name
    Type = "Lambda"
  })

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
      last_modified,
    ]
  }
}

# Create placeholder zip file for initial deployment
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = <<EOF
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Placeholder function - will be replaced by CI/CD'
    }
EOF
    filename = "lambda_function.py"
  }
}

###########################################
# SQS EVENT SOURCE MAPPING
###########################################

resource "aws_lambda_event_source_mapping" "weather_processor_sqs" {
  event_source_arn = aws_sqs_queue.weather_queue.arn
  function_name    = aws_lambda_function.weather_functions["weather_processor"].arn
  batch_size       = 10

  depends_on = [aws_iam_role_policy.lambda_execution_policy]
}

###########################################
# API GATEWAY
###########################################

resource "aws_api_gateway_rest_api" "weather_api" {
  name        = "${local.name_prefix}-api"
  description = "Weather Processing API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(local.common_tags, {
    Name = "Weather API Gateway"
    Type = "API"
  })
}

# Custom authorizer
resource "aws_api_gateway_authorizer" "weather_authorizer" {
  name                             = "${local.name_prefix}-authorizer"
  rest_api_id                      = aws_api_gateway_rest_api.weather_api.id
  authorizer_uri                   = aws_lambda_function.weather_functions["authorizer"].invoke_arn
  authorizer_credentials           = aws_iam_role.api_gateway_invocation_role.arn
  type                             = "REQUEST"
  identity_source                  = "method.request.header.Authorization"
  authorizer_result_ttl_in_seconds = 300
}

# API Gateway resources and methods
resource "aws_api_gateway_resource" "weather_resource" {
  rest_api_id = aws_api_gateway_rest_api.weather_api.id
  parent_id   = aws_api_gateway_rest_api.weather_api.root_resource_id
  path_part   = "weather"
}

resource "aws_api_gateway_method" "weather_post" {
  rest_api_id   = aws_api_gateway_rest_api.weather_api.id
  resource_id   = aws_api_gateway_resource.weather_resource.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.weather_authorizer.id

  request_parameters = {
    "method.request.header.Authorization" = true
  }
}

# Enable CORS
resource "aws_api_gateway_method" "weather_options" {
  rest_api_id   = aws_api_gateway_rest_api.weather_api.id
  resource_id   = aws_api_gateway_resource.weather_resource.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "weather_post_integration" {
  rest_api_id = aws_api_gateway_rest_api.weather_api.id
  resource_id = aws_api_gateway_resource.weather_resource.id
  http_method = aws_api_gateway_method.weather_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.weather_functions["weather_fetcher"].invoke_arn
}

# CORS integration
resource "aws_api_gateway_integration" "weather_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.weather_api.id
  resource_id = aws_api_gateway_resource.weather_resource.id
  http_method = aws_api_gateway_method.weather_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_method_response" "weather_options_response" {
  rest_api_id = aws_api_gateway_rest_api.weather_api.id
  resource_id = aws_api_gateway_resource.weather_resource.id
  http_method = aws_api_gateway_method.weather_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "weather_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.weather_api.id
  resource_id = aws_api_gateway_resource.weather_resource.id
  http_method = aws_api_gateway_method.weather_options.http_method
  status_code = aws_api_gateway_method_response.weather_options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

###########################################
# LAMBDA PERMISSIONS
###########################################

resource "aws_lambda_permission" "api_gateway_lambda_fetcher" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weather_functions["weather_fetcher"].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.weather_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "api_gateway_authorizer" {
  statement_id  = "AllowExecutionFromAPIGatewayAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weather_functions["authorizer"].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.weather_api.execution_arn}/authorizers/*"
}

###########################################
# API GATEWAY DEPLOYMENT
###########################################

resource "aws_api_gateway_deployment" "weather_deployment" {
  depends_on = [
    aws_api_gateway_method.weather_post,
    aws_api_gateway_method.weather_options,
    aws_api_gateway_integration.weather_post_integration,
    aws_api_gateway_integration.weather_options_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.weather_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.weather_resource.id,
      aws_api_gateway_method.weather_post.id,
      aws_api_gateway_method.weather_options.id,
      aws_api_gateway_integration.weather_post_integration.id,
      aws_api_gateway_integration.weather_options_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "weather_stage" {
  deployment_id = aws_api_gateway_deployment.weather_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.weather_api.id
  stage_name    = var.environment

  # Enable logging and tracing
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      error          = "$context.error.message"
      errorType      = "$context.error.messageString"
    })
  }

  tags = merge(local.common_tags, {
    Name = "Weather API Stage"
    Type = "API"
  })
}

resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Name = "API Gateway Logs"
    Type = "Logs"
  })
}

###########################################
# CLOUDWATCH ALARMS (Optional)
###########################################

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.lambda_functions

  alarm_name          = "${each.value.name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors lambda errors"
  alarm_actions       = [aws_sns_topic.weather_notifications.arn]

  dimensions = {
    FunctionName = each.value.name
  }

  tags = local.common_tags
}

###########################################
# OUTPUTS
###########################################

output "api_gateway_url" {
  description = "URL of the API Gateway"
  value       = aws_api_gateway_stage.weather_stage.invoke_url
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.weather_api.id
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for weather data"
  value       = aws_s3_bucket.weather_bucket.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.weather_bucket.arn
}

output "sqs_queue_url" {
  description = "URL of the SQS queue"
  value       = aws_sqs_queue.weather_queue.id
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.weather_queue.arn
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic"
  value       = aws_sns_topic.weather_notifications.arn
}

output "lambda_function_names" {
  description = "Names of the Lambda functions"
  value = {
    for k, v in aws_lambda_function.weather_functions : k => v.function_name
  }
}

output "secrets_manager_secret_name" {
  description = "Name of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.weather_api_key.name
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log group names"
  value = {
    for k, v in aws_cloudwatch_log_group.lambda_logs : k => v.name
  }
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region"
  value       = data.aws_region.current.name
}
