import unittest
from unittest.mock import patch, MagicMock

from ..authorizer.lambda_function import lambda_handler


class TestAuthorizerLambdaFunction(unittest.TestCase):
    @patch('src.lambda.authorizer.lambda_function.logging.getLogger')
    @patch('src.lambda.authorizer.lambda_function.os.environ', {'LOG_LEVEL': 'DEBUG'})
    def test_valid_token_allowed(self, mock_get_logger):
        event = {
            'headers': {
                'Authorization': 'Bearer valid-JWT-001'
            },
            'methodArn': 'arn:aws:execute-api:region:account-id:api-id/stage/GET/resource'
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        expected_response = {
            'principalId': 'user123',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Allow',
                        'Resource': event['methodArn']
                    }
                ]
            },
            'context': {
                'userId': 'user123',
                'tokenValid': 'true'
            }
        }
        self.assertEqual(expected_response, response)


    @patch('src.lambda.authorizer.lambda_function.logging.getLogger')
    @patch('src.lambda.authorizer.lambda_function.os.environ', {'LOG_LEVEL': 'INFO'})
    def test_invalid_token_denied(self, mock_get_logger):
        event = {
            'headers': {
                'Authorization': 'invalid-token'
            },
            'methodArn': 'arn:aws:execute-api:region:account-id:api-id/stage/POST/resource'
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        expected_response = {
            'principalId': 'unauthorized',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': event['methodArn']
                    }
                ]
            },
            'context': {
                'userId': 'unauthorized',
                'tokenValid': 'false'
            }
        }
        self.assertEqual(expected_response, response)


    @patch('src.lambda.authorizer.lambda_function.logging.getLogger')
    def test_missing_token_denied(self, mock_get_logger):
        event = {
            'headers': {},
            'methodArn': 'arn:aws:execute-api:region:account-id:api-id/stage/DELETE/resource'
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        expected_response = {
            'principalId': 'unauthorized',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': event['methodArn']
                    }
                ]
            },
            'context': {
                'userId': 'unauthorized',
                'tokenValid': 'false'
            }
        }
        self.assertEqual(expected_response, response)


if __name__ == '__main__':
    unittest.main()
