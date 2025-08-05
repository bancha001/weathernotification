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
        date_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y/%m/%d-%H-%M-%S-%f')
        s3_key = f"weather-data/{date_str}.json"

        # Extract data from input event
        weather_body_string = event['Records'][0]['body']
        weather_body_json = json.loads(weather_body_string)
        weather_body_data = weather_body_json['data']
        formatted_data = json.dumps(weather_body_data, indent=2)

        # Store processed data in S3
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=formatted_data,
            ContentType='application/json'
        )
        handle_notification(weather_body_json, sns_topic_arn)

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

# Send a notification based on a notification type
def handle_notification(weather_body, sns_topic_arn):
    notification_type = weather_body['notification_type']
    body_message =  weather_body['data']['weather'][0]['description']
    city_name = weather_body['city_name']
    subject_text = f"Weather condition for {city_name}"
    if notification_type == 'sms' or notification_type == 'both':
        sns_client = boto3.client('sns')
        phone_number = weather_body['phone_number']
        handle_subscription(sns_topic_arn, sns_client, 'sms', phone_number)

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=f"{subject_text} - {body_message}",
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': 'WEATHER'
                },
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
    if notification_type == 'email' or notification_type == 'both':
        sns_client = boto3.client('sns')
        email = weather_body['email']

        handle_subscription(sns_topic_arn, sns_client, 'email', email)

        sns_client.publish(
            TopicArn = sns_topic_arn,
            Subject = subject_text,
            Message = f"Weather Condition for {city_name} - {body_message}",
            MessageStructure = 'text',
            MessageAttributes = {
                'email': {
                    'DataType': 'String',
                    'StringValue': email
                }
            }
        )

def handle_subscription( sns_topic_arn, sns_client, protocol, endpoint):
    response = sns_client.list_subscriptions_by_topic(TopicArn=sns_topic_arn)
    is_subscribed = False
    for subscription in response['Subscriptions']:
        if subscription['Protocol'] == protocol and subscription['Endpoint'] == endpoint :
            is_subscribed = True
            break

    if not is_subscribed :
        sns_client.subscribe(
            TopicArn = sns_topic_arn,
            Protocol = protocol,
            Endpoint = endpoint
        )



