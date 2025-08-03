import json
import os

def lambda_handler(event, context):
    """
    Custom API Gateway Authorizer Lambda
    """

    # Get the authorization token from the event
    token = event.get('headers', {}).get('Authorization')
    method_arn = event.get('methodArn', '')
    print(f"Authorization header: {token}")

    # Simple token validation (replace with your actual auth logic)
    # In production, you might validate JWT tokens, API keys, etc.
    valid_tokens = [
        'Bearer valid-JWT-001',
        'Bearer valid-JWT-002'
    ]

    try:
        # Validate the token
        if token in valid_tokens:
            effect = 'Allow'
            principal_id = 'user123'  # Could extract from token
        else:
            effect = 'Deny'
            principal_id = 'unauthorized'

        # Build the policy document
        policy_document = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': method_arn
                }
            ]
        }

        # Return the authorization response
        auth_response = {
            'principalId': principal_id,
            'policyDocument': policy_document,
            'context': {
                'userId': principal_id,
                'tokenValid': str(effect == 'Allow').lower()
            }
        }

        return auth_response

    except Exception as e:
        print(f"Authorization error: {str(e)}")
        # In case of error, deny access
        return {
            'principalId': 'unauthorized',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': method_arn
                    }
                ]
            }
        }
