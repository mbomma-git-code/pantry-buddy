import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class BedrockAgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const foundationModelId = 'anthropic.claude-3-5-haiku-20241022-v1:0';

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
  }
}
