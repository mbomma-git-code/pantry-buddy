import * as cdk from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/** Titan Text Embeddings V2 (default 1024-d). Confirmed available in us-east-2 for Knowledge Bases. */
export const TITAN_EMBED_TEXT_V2_MODEL_ID = 'amazon.titan-embed-text-v2:0';
export const TITAN_EMBED_TEXT_V2_DIMENSIONS = 1024;

const VECTOR_INDEX_NAME = 'pantrybuddy-recipes';
const VECTOR_FIELD = 'bedrock-knowledge-base-default-vector';
const TEXT_FIELD = 'AMAZON_BEDROCK_TEXT_CHUNK';
const METADATA_FIELD = 'AMAZON_BEDROCK_METADATA';

export interface RecipeKnowledgeBaseProps {
  /** Data bucket that holds `kb/structured/` corpus objects. */
  dataBucket: s3.IBucket;
  /** S3 key prefix for the structured corpus (trailing slash recommended). */
  structuredPrefix?: string;
}

/**
 * Bedrock Knowledge Base over OpenSearch Serverless + Titan Embeddings V2,
 * with an S3 data source on `kb/structured/`.
 */
export class RecipeKnowledgeBase extends Construct {
  readonly knowledgeBase: bedrock.CfnKnowledgeBase;
  readonly dataSource: bedrock.CfnDataSource;
  readonly collection: opensearchserverless.CfnCollection;
  readonly knowledgeBaseRole: iam.Role;
  readonly syncRole: iam.Role;
  readonly knowledgeBaseId: string;
  readonly dataSourceId: string;
  readonly structuredPrefix: string;

  constructor(scope: Construct, id: string, props: RecipeKnowledgeBaseProps) {
    super(scope, id);

    this.structuredPrefix = props.structuredPrefix ?? 'kb/structured/';
    const stack = cdk.Stack.of(this);
    const collectionName = 'pb-recipes-kb';
    const embeddingModelArn = `arn:${stack.partition}:bedrock:${stack.region}::foundation-model/${TITAN_EMBED_TEXT_V2_MODEL_ID}`;

    this.knowledgeBaseRole = new iam.Role(this, 'KnowledgeBaseRole', {
      assumedBy: new iam.PrincipalWithConditions(new iam.ServicePrincipal('bedrock.amazonaws.com'), {
        StringEquals: { 'aws:SourceAccount': stack.account },
        ArnLike: {
          'aws:SourceArn': `arn:${stack.partition}:bedrock:${stack.region}:${stack.account}:knowledge-base/*`,
        },
      }),
      description: 'Bedrock Knowledge Base role for PantryBuddy structured recipe corpus',
    });

    this.knowledgeBaseRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'BedrockInvokeEmbeddingModel',
        actions: ['bedrock:InvokeModel'],
        resources: [embeddingModelArn],
      })
    );
    props.dataBucket.grantRead(this.knowledgeBaseRole, `${this.structuredPrefix}*`);

    // Deployer / sync principals need data-plane access to create the vector index.
    const accountRootArn = `arn:${stack.partition}:iam::${stack.account}:root`;

    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OssEncryptionPolicy', {
      name: `${collectionName}-enc`,
      type: 'encryption',
      description: 'Encrypt PantryBuddy recipe KB OpenSearch Serverless collection',
      policy: JSON.stringify({
        Rules: [{ ResourceType: 'collection', Resource: [`collection/${collectionName}`] }],
        AWSOwnedKey: true,
      }),
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OssNetworkPolicy', {
      name: `${collectionName}-net`,
      type: 'network',
      description: 'Public network access for Bedrock KB and index management',
      policy: JSON.stringify([
        {
          Rules: [
            { ResourceType: 'collection', Resource: [`collection/${collectionName}`] },
            { ResourceType: 'dashboard', Resource: [`collection/${collectionName}`] },
          ],
          AllowFromPublic: true,
        },
      ]),
    });

    this.collection = new opensearchserverless.CfnCollection(this, 'OssCollection', {
      name: collectionName,
      type: 'VECTORSEARCH',
      description: 'Vector store for PantryBuddy structured recipe Knowledge Base',
      standbyReplicas: 'DISABLED',
    });
    this.collection.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);
    this.collection.addDependency(encryptionPolicy);
    this.collection.addDependency(networkPolicy);

    this.knowledgeBaseRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'OpenSearchServerlessApiAccess',
        actions: ['aoss:APIAccessAll'],
        resources: [this.collection.attrArn],
      })
    );

    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'OssDataAccessPolicy', {
      name: `${collectionName}-data`,
      type: 'data',
      description: 'Data access for Bedrock KB role and account index management',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${collectionName}`],
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DeleteCollectionItems',
                'aoss:UpdateCollectionItems',
                'aoss:DescribeCollectionItems',
              ],
            },
            {
              ResourceType: 'index',
              Resource: [`index/${collectionName}/*`],
              Permission: [
                'aoss:CreateIndex',
                'aoss:DeleteIndex',
                'aoss:UpdateIndex',
                'aoss:DescribeIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument',
              ],
            },
          ],
          Principal: [this.knowledgeBaseRole.roleArn, accountRootArn],
        },
      ]),
    });
    dataAccessPolicy.addDependency(this.collection);

    // Native CFN index resource (not yet typed in aws-cdk-lib 2.170).
    const vectorIndex = new cdk.CfnResource(this, 'OssVectorIndex', {
      type: 'AWS::OpenSearchServerless::Index',
      properties: {
        CollectionEndpoint: this.collection.attrCollectionEndpoint,
        IndexName: VECTOR_INDEX_NAME,
        Settings: {
          Index: {
            Knn: true,
            KnnAlgoParamEfSearch: 512,
          },
        },
        Mappings: {
          Properties: {
            [METADATA_FIELD]: {
              Type: 'text',
              Index: false,
            },
            [TEXT_FIELD]: {
              Type: 'text',
              Index: true,
            },
            [VECTOR_FIELD]: {
              Type: 'knn_vector',
              Dimension: TITAN_EMBED_TEXT_V2_DIMENSIONS,
              Method: {
                Name: 'hnsw',
                Engine: 'faiss',
                SpaceType: 'l2',
                Parameters: {
                  M: 16,
                  EfConstruction: 512,
                },
              },
            },
          },
        },
      },
    });
    vectorIndex.addDependency(this.collection);
    vectorIndex.addDependency(dataAccessPolicy);

    this.knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: 'pantrybuddy-structured-recipes',
      description: 'Structured recipe corpus (Corpus A) for PantryBuddy v3 chat RAG',
      roleArn: this.knowledgeBaseRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn,
          embeddingModelConfiguration: {
            bedrockEmbeddingModelConfiguration: {
              dimensions: TITAN_EMBED_TEXT_V2_DIMENSIONS,
            },
          },
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.collection.attrArn,
          vectorIndexName: VECTOR_INDEX_NAME,
          fieldMapping: {
            vectorField: VECTOR_FIELD,
            textField: TEXT_FIELD,
            metadataField: METADATA_FIELD,
          },
        },
      },
    });
    this.knowledgeBase.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);
    this.knowledgeBase.addDependency(vectorIndex);
    this.knowledgeBase.node.addDependency(this.knowledgeBaseRole);

    this.dataSource = new bedrock.CfnDataSource(this, 'StructuredDataSource', {
      name: 'structured-recipes',
      description: 'S3 kb/structured/ recipe documents and metadata sidecars',
      knowledgeBaseId: this.knowledgeBase.attrKnowledgeBaseId,
      dataDeletionPolicy: 'DELETE',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: props.dataBucket.bucketArn,
          inclusionPrefixes: [this.structuredPrefix],
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          // Local builder already emits one retrieval unit per recipe file.
          chunkingStrategy: 'NONE',
        },
      },
    });

    this.syncRole = new iam.Role(this, 'KbSyncRole', {
      assumedBy: new iam.AccountRootPrincipal(),
      description:
        'Role for uploading kb/structured/ objects and starting Bedrock KB ingestion jobs',
    });
    props.dataBucket.grantReadWrite(this.syncRole, `${this.structuredPrefix}*`);
    props.dataBucket.grantReadWrite(this.syncRole, 'kb/kb_manifest.json');
    this.syncRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'ListBucketForKbPrefix',
        actions: ['s3:ListBucket'],
        resources: [props.dataBucket.bucketArn],
        conditions: {
          StringLike: { 's3:prefix': ['kb/*'] },
        },
      })
    );
    this.syncRole.addToPolicy(
      new iam.PolicyStatement({
        sid: 'StartKnowledgeBaseIngestion',
        actions: [
          'bedrock:StartIngestionJob',
          'bedrock:GetIngestionJob',
          'bedrock:ListIngestionJobs',
        ],
        resources: [this.knowledgeBase.attrKnowledgeBaseArn],
      })
    );

    this.knowledgeBaseId = this.knowledgeBase.attrKnowledgeBaseId;
    this.dataSourceId = this.dataSource.attrDataSourceId;
  }
}
