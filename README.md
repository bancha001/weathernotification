## Weather API Infrastructure Deployment

This repository contains GitHub Actions workflows to deploy a serverless weather processing system on AWS.

### Architecture Components
![Alt Text](architectural-diagram.png)

- **API Gateway**: Entry point for weather requests
- **Lambda Authorizer**: Custom authorization for API requests
- **Weather Fetcher Lambda**: Fetches weather data from external APIs
- **SQS Queue**: Decouples weather fetching from processing
- **Weather Processor Lambda**: Processes and stores weather data
- **S3 Bucket**: Stores processed weather data
- **SNS Topic**: Sends notifications for extreme weather
- **Secrets Manager**: Securely stores weather API keys

### Setup Instructions

1. **Fork/Clone this repository**

2. **Set up GitHub Secrets** (Repository Settings > Secrets and variables > Actions):
   ```
   AWS_ACCESS_KEY_ID: Your AWS access key
   AWS_SECRET_ACCESS_KEY: Your AWS secret key
   WEATHER_API_KEY: Your weather API key (e.g., OpenWeatherMap)
   ```

3. **Configure Terraform Backend** (Optional but recommended):
    - Create an S3 bucket for Terraform state
    - Update the backend configuration in `infrastructure/main.tf`

4. **Create the directory structure**:
   ```
   project-root/
   ├── .github/workflows/
   ├── infrastructure/
   ├── lambda/
   │   ├── weather-fetcher/
   │   ├── weather-processor/
   │   └── authorizer/
   └── README.md
   ```

5. **Deploy Infrastructure**:
    - Push changes to the `main` branch
    - GitHub Actions will automatically deploy the infrastructure
    - Check the Actions tab for deployment status

### Usage

1. **Get API Gateway URL** from AWS Console
2. **Import Postman Collection under src/postman**:
   - Create a new environment in WEATHER_INTEGRATION_DEVELOPMENT
   - Add API_GATEWAY_URL variable and supply value from step 1
   - Add EMAIL variable by using your test email address
   - Add PHONE_NUMBER variable by using your test phone number
3. **Run the Postman requests and verify the result**:
### Monitoring

- CloudWatch Logs for each Lambda function
- SNS notifications for extreme weather conditions
- S3 bucket contains processed weather data organized by date

### Cleanup

Run the cleanup workflow manually from the Actions tab to destroy all resources.

### Security Notes

- API keys are stored in AWS Secrets Manager
- Lambda functions use least-privilege IAM roles
- S3 bucket has server-side encryption enabled
- Custom authorizer validates requests before processing
