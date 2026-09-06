import { App } from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { PublicApiStack } from '../lib/public-api-stack';

test('creates a restricted evaluate API and least-privilege runtime grant', () => {
  const app = new App();
  const template = Template.fromStack(new PublicApiStack(app, 'TestStack'));

  template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
    RouteKey: 'POST /api/evaluate',
  });
  template.hasResourceProperties('AWS::Lambda::Function', {
    Timeout: 28,
    ReservedConcurrentExecutions: Match.absent(),
    Environment: { Variables: { DEMO_PROPERTY_UNIT: 'U4' } },
  });
  template.hasResourceProperties('AWS::ApiGatewayV2::Stage', {
    DefaultRouteSettings: {
      ThrottlingBurstLimit: 5,
      ThrottlingRateLimit: 2,
    },
  });
  template.hasResourceProperties('AWS::IAM::Policy', {
    PolicyDocument: {
      Statement: Match.arrayWith([
        Match.objectLike({
          Action: 'bedrock-agentcore:InvokeAgentRuntime',
          Resource: [
            { Ref: 'AgentRuntimeArn' },
            {
              'Fn::Join': [
                '',
                [
                  { Ref: 'AgentRuntimeArn' },
                  '/runtime-endpoint/DEFAULT',
                ],
              ],
            },
          ],
        }),
      ]),
    },
  });

  const policies = template.findResources('AWS::IAM::Policy');
  const statements = Object.values(policies).flatMap((policy: any) =>
    policy.Properties.PolicyDocument.Statement
  );
  const invokeStatement = statements.find(
    (statement: any) => statement.Action === 'bedrock-agentcore:InvokeAgentRuntime'
  );
  expect(invokeStatement).toBeDefined();
  expect(invokeStatement.Resource).not.toBe('*');
  expect(invokeStatement.Resource).toEqual([
    { Ref: 'AgentRuntimeArn' },
    {
      'Fn::Join': [
        '',
        [{ Ref: 'AgentRuntimeArn' }, '/runtime-endpoint/DEFAULT'],
      ],
    },
  ]);
});
