import * as path from 'path';
import {
  CfnOutput,
  CfnParameter,
  Duration,
  Stack,
  StackProps,
  aws_apigatewayv2 as apigwv2,
  aws_apigatewayv2_integrations as integrations,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

export class PublicApiStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const runtimeArn = new CfnParameter(this, 'AgentRuntimeArn', {
      type: 'String',
      description: 'ARN of the deployed MaintAutopilot AgentCore runtime.',
      allowedPattern: '^arn:aws[a-zA-Z-]*:bedrock-agentcore:us-east-1:[0-9]{12}:runtime/.+$',
    });
    const allowedOrigin = new CfnParameter(this, 'AllowedOrigin', {
      type: 'String',
      description: 'Exact HTTPS origin of the competition frontend (no trailing slash).',
      allowedPattern: '^https://[^/]+$',
    });

    const handlerLogs = new logs.LogGroup(this, 'EvaluateHandlerLogs', {
      retention: logs.RetentionDays.ONE_WEEK,
    });

    const handler = new lambda.Function(this, 'EvaluateHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(process.cwd(), 'lambda')),
      timeout: Duration.seconds(28),
      memorySize: 256,
      environment: {
        AGENT_RUNTIME_ARN: runtimeArn.valueAsString,
        AWS_AGENTCORE_REGION: 'us-east-1',
        DEMO_PROPERTY_UNIT: 'U4',
        DEMO_PROPERTY_AUTHORITY_USD: '200',
        MAX_REPORT_LENGTH: '4000',
      },
      logGroup: handlerLogs,
      tracing: lambda.Tracing.ACTIVE,
    });

    handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:InvokeAgentRuntime'],
      resources: [
        runtimeArn.valueAsString,
        `${runtimeArn.valueAsString}/runtime-endpoint/DEFAULT`,
      ],
    }));

    const api = new apigwv2.HttpApi(this, 'PublicApi', {
      apiName: 'MaintAutopilotPublicApi',
      corsPreflight: {
        allowOrigins: [allowedOrigin.valueAsString],
        allowMethods: [apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
        allowHeaders: ['content-type', 'x-request-id'],
        exposeHeaders: ['x-request-id'],
        maxAge: Duration.hours(1),
      },
      createDefaultStage: false,
    });

    api.addRoutes({
      path: '/api/evaluate',
      methods: [apigwv2.HttpMethod.POST],
      integration: new integrations.HttpLambdaIntegration('EvaluateIntegration', handler),
    });

    const stage = new apigwv2.CfnStage(this, 'DefaultStage', {
      apiId: api.apiId,
      stageName: '$default',
      autoDeploy: true,
      defaultRouteSettings: {
        throttlingBurstLimit: 5,
        throttlingRateLimit: 2,
      },
    });
    stage.node.addDependency(api);

    new CfnOutput(this, 'ApiUrl', { value: api.apiEndpoint });
  }
}
