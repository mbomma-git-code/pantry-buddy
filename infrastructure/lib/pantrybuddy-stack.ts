import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export class PantryBuddyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const backendPath = path.join(__dirname, '../../backend');
    const recipeDataPath = path.join(__dirname, '../../data/recipes_json');
    const frontendPath = path.join(__dirname, '../../frontend');

    // --- S3: Static website bucket (frontend) ---
    const websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName: undefined, // let CDK generate a unique name
      blockPublicAccess: new s3.BlockPublicAccess({
        blockPublicAcls: false,
        blockPublicPolicy: false,
        ignorePublicAcls: false,
        restrictPublicBuckets: false,
      }),
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    websiteBucket.addToResourcePolicy(
      new cdk.aws_iam.PolicyStatement({
        sid: 'PublicReadGetObject',
        effect: cdk.aws_iam.Effect.ALLOW,
        principals: [new cdk.aws_iam.AnyPrincipal()],
        actions: ['s3:GetObject'],
        resources: [websiteBucket.arnForObjects('*')],
      })
    );

    // --- S3: Recipe data bucket (Lambda reads from here) ---
    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: undefined,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Deploy recipe JSON files into the data bucket under recipes_json/
    new s3deploy.BucketDeployment(this, 'DeployRecipeData', {
      sources: [s3deploy.Source.asset(recipeDataPath)],
      destinationBucket: dataBucket,
      destinationKeyPrefix: 'recipes_json/',
      memoryLimit: 512,
    });

    // --- Lambda: Meal plan generator ---
    const mealPlanLambda = new lambda.Function(this, 'MealPlanFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset(backendPath),
      environment: {
        S3_BUCKET_NAME: dataBucket.bucketName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    dataBucket.grantRead(mealPlanLambda);

    // --- API Gateway: REST API with CORS ---
    const api = new apigateway.RestApi(this, 'MealPlanApi', {
      restApiName: 'PantryBuddy Meal Plan API',
      description: 'API for PantryBuddy weekly meal plan generation',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
      deployOptions: {
        stageName: 'prod',
      },
    });

    const lambdaIntegration = new apigateway.LambdaIntegration(mealPlanLambda);
    const generateMealPlan = api.root.addResource('generate-meal-plan');
    generateMealPlan.addMethod('POST', lambdaIntegration);

    // --- Optional: Deploy frontend to the website bucket (run once or via CI) ---
    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [s3deploy.Source.asset(frontendPath)],
      destinationBucket: websiteBucket,
      memoryLimit: 512,
    });

    // --- Outputs ---
    new cdk.CfnOutput(this, 'WebsiteBucketName', {
      value: websiteBucket.bucketName,
      description: 'S3 bucket for static website hosting',
      exportName: 'PantryBuddy-WebsiteBucketName',
    });
    new cdk.CfnOutput(this, 'WebsiteURL', {
      value: websiteBucket.bucketWebsiteUrl,
      description: 'Static website URL (use this or CloudFront later)',
      exportName: 'PantryBuddy-WebsiteURL',
    });
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: dataBucket.bucketName,
      description: 'S3 bucket for recipe JSON data',
      exportName: 'PantryBuddy-DataBucketName',
    });
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway base URL (set API_BASE_URL in frontend config)',
      exportName: 'PantryBuddy-ApiEndpoint',
    });
    new cdk.CfnOutput(this, 'GenerateMealPlanUrl', {
      value: `${api.url}generate-meal-plan`,
      description: 'Full URL for POST /generate-meal-plan',
      exportName: 'PantryBuddy-GenerateMealPlanUrl',
    });
  }
}
