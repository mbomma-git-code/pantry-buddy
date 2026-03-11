import * as cdk from 'aws-cdk-lib';
import * as path from 'path';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export class BedrockAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const backendPath = path.join(__dirname, '../../backend');
    const foundationModelId = 'anthropic.claude-3-5-haiku-20241022-v1:0';
    const preferencesTable = new dynamodb.Table(this, 'DietaryPreferencesTable', {
      partitionKey: {
        name: 'userId',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const preferencesLambda = new lambda.Function(this, 'DietaryPreferencesFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'dietary_preferences_lambda.lambda_handler',
      code: lambda.Code.fromAsset(backendPath),
      environment: {
        DIETARY_PREFERENCES_TABLE: preferencesTable.tableName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    preferencesTable.grantReadWriteData(preferencesLambda);

    const bedrockAgentRole = new iam.Role(this, 'DieticianBedrockAgentRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Resource role used by the PantryBuddy Bedrock agent',
    });

    bedrockAgentRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:${cdk.Aws.PARTITION}:bedrock:${cdk.Aws.REGION}::foundation-model/${foundationModelId}`,
        ],
      })
    );
    bedrockAgentRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['lambda:InvokeFunction'],
        resources: [preferencesLambda.functionArn],
      })
    );

    const bedrockAgent = new cdk.CfnResource(this, 'DieticianBedrockAgent', {
      type: 'AWS::Bedrock::Agent',
      properties: {
        AgentName: 'pantrybuddy-dietician-7day-agent',
        Description: 'Dietician agent for personalized 7-day meal plans',
        FoundationModel: foundationModelId,
        AgentResourceRoleArn: bedrockAgentRole.roleArn,
        AutoPrepare: true,
        Instruction:
          'You are a dietician who can create meal plan according to the user preferences. Curate a 7 day 4 meals a day plan.',
      },
    });

    const preferencesActionOpenApiSchema = {
      openapi: '3.0.1',
      info: {
        title: 'Dietary Preferences API',
        version: '1.0.0',
      },
      paths: {
        '/dietary-preferences': {
          post: {
            operationId: 'addDietaryPreferences',
            description: 'Add dietary preferences for a user.',
            requestBody: {
              required: true,
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    required: ['userId', 'preferences'],
                    properties: {
                      userId: { type: 'string' },
                      preferences: {
                        type: 'array',
                        items: { type: 'string' },
                      },
                    },
                  },
                },
              },
            },
            responses: {
              '200': {
                description: 'Dietary preferences created.',
              },
            },
          },
        },
        '/dietary-preferences/{userId}': {
          put: {
            operationId: 'updateDietaryPreferences',
            description: 'Update dietary preferences for a user.',
            parameters: [
              {
                name: 'userId',
                in: 'path',
                required: true,
                schema: { type: 'string' },
              },
            ],
            requestBody: {
              required: true,
              content: {
                'application/json': {
                  schema: {
                    type: 'object',
                    required: ['preferences'],
                    properties: {
                      preferences: {
                        type: 'array',
                        items: { type: 'string' },
                      },
                    },
                  },
                },
              },
            },
            responses: {
              '200': {
                description: 'Dietary preferences updated.',
              },
            },
          },
        },
      },
    };

    const preferencesActionGroup = new cdk.CfnResource(this, 'DietaryPreferencesActionGroup', {
      type: 'AWS::Bedrock::AgentActionGroup',
      properties: {
        AgentId: bedrockAgent.getAtt('AgentId').toString(),
        AgentVersion: 'DRAFT',
        ActionGroupName: 'DietaryPreferencesActions',
        Description: 'Action group for creating and updating dietary preferences.',
        ActionGroupExecutor: {
          Lambda: preferencesLambda.functionArn,
        },
        ApiSchema: {
          Payload: JSON.stringify(preferencesActionOpenApiSchema),
        },
      },
    });
    preferencesActionGroup.addDependency(bedrockAgent);

    new lambda.CfnPermission(this, 'AllowBedrockInvokePreferencesLambda', {
      action: 'lambda:InvokeFunction',
      functionName: preferencesLambda.functionName,
      principal: 'bedrock.amazonaws.com',
      sourceArn: bedrockAgent.getAtt('AgentArn').toString(),
    }).addDependency(preferencesActionGroup);

    new cdk.CfnOutput(this, 'BedrockAgentId', {
      value: bedrockAgent.getAtt('AgentId').toString(),
      description: 'Bedrock dietician agent ID',
      exportName: 'PantryBuddy-DieticianBedrockAgentId',
    });

    new cdk.CfnOutput(this, 'BedrockAgentRoleArn', {
      value: bedrockAgentRole.roleArn,
      description: 'IAM role ARN for Bedrock dietician agent',
      exportName: 'PantryBuddy-DieticianBedrockAgentRoleArn',
    });

    new cdk.CfnOutput(this, 'DietaryPreferencesTableName', {
      value: preferencesTable.tableName,
      description: 'DynamoDB table for user dietary preferences',
      exportName: 'PantryBuddy-DietaryPreferencesTableName',
    });

    new cdk.CfnOutput(this, 'DietaryPreferencesLambdaArn', {
      value: preferencesLambda.functionArn,
      description: 'Lambda ARN for dietary preferences Bedrock action group',
      exportName: 'PantryBuddy-DietaryPreferencesLambdaArn',
    });
  }
}
