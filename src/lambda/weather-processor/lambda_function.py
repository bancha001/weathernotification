import json
import boto3
import os
from datetime import datetime
import logging

log_level_name = os.environ.get('LOG_LEVEL', 'INFO')
log_level = getattr(logging, log_level_name.upper(), logging.INFO)
logger = logging.getLogger()
logger.setLevel(log_level)

def lambda_handler(event, context):
    """
    Weather Processor Lambda - Processes weather data from SQS then stores in S3 and send notification to SNS
    """

    logger.info(f"Received event: {json.dumps(event)}")
    # Initialize AWS clients
    s3_client = boto3.client('s3')
    sns_client = boto3.client('sns')

    s3_bucket = os.environ['S3_BUCKET_NAME']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']

    processed_messages = []

    try:
        # Generate S3 key with date partitioning
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')
        date_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y/%m/%d-%S-%f')
        s3_key = f"weather-data/{date_str}.json"

        # Store processed data in S3
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(event, indent=2),
            ContentType='application/json'
        )
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject='Weather Alert',
            Message=json.dumps(event, indent=2)
        )

        return {
            'statusCode': 200,
            'body': event
        }

    except Exception as e:
        print(f"Error processing weather data: {str(e)}")

        # Send error notification
        try:
            error_message = {
                'error': 'Weather processing failed',
                'details': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject="Weather Processing Error",
                Message=json.dumps(error_message, indent=2)
            )
        except:
            pass  # Don't fail if notification fails

        raise e
