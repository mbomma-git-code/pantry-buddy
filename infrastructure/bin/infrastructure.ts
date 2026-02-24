#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PantryBuddyStack } from '../lib/pantrybuddy-stack';

const app = new cdk.App();

new PantryBuddyStack(app, 'PantryBuddyStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-2',
  },
  description: 'PantryBuddy: S3 static hosting, Lambda meal-plan API, recipe data',
});

app.synth();
