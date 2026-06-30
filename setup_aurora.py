"""
setup_aurora.py
One-time run: creates Aurora Serverless v2 pgvector cluster.
After running, copy the ARNs printed at the end into your .env file.

Usage:
    python setup_aurora.py
"""

import boto3
import json
import time
import config

rds    = boto3.client("rds",              region_name=config.AWS_REGION)
sm     = boto3.client("secretsmanager",   region_name=config.AWS_REGION)

CLUSTER_ID = "jay-exer-pgvector"
DB_NAME    = config.AURORA_DB_NAME
SECRET_NAME= "jay-exer-pgvector-creds"
DB_USER    = "jaydbadmin"
DB_PASS    = "JayExer2024!"   # change before production use


def create_secret():
    print("Creating Secrets Manager entry...")
    try:
        r = sm.create_secret(
            Name        = SECRET_NAME,
            Description = "Aurora pgvector credentials for jay-exer KB",
            SecretString= json.dumps({"username": DB_USER, "password": DB_PASS})
        )
        arn = r["ARN"]
    except sm.exceptions.ResourceExistsException:
        arn = sm.describe_secret(SecretId=SECRET_NAME)["ARN"]
        print("  Secret already exists, reusing.")
    print(f"  Secret ARN: {arn}")
    return arn


def create_cluster():
    print("Creating Aurora Serverless v2 cluster (pgvector)...")
    try:
        r = rds.create_db_cluster(
            DBClusterIdentifier = CLUSTER_ID,
            Engine              = "aurora-postgresql",
            EngineVersion       = "16.4",
            MasterUsername      = DB_USER,
            MasterUserPassword  = DB_PASS,
            DatabaseName        = DB_NAME,
            EnableHttpEndpoint  = True,
            ServerlessV2ScalingConfiguration = {
                "MinCapacity": 0.5,
                "MaxCapacity": 4.0
            }
        )
        arn = r["DBCluster"]["DBClusterArn"]
    except rds.exceptions.DBClusterAlreadyExistsFault:
        arn = rds.describe_db_clusters(
            DBClusterIdentifier=CLUSTER_ID
        )["DBClusters"][0]["DBClusterArn"]
        print("  Cluster already exists, reusing.")

    print(f"  Cluster ARN: {arn}")
    return arn


def wait_for_cluster():
    print("Waiting for cluster to become available (2-5 min)...")
    while True:
        status = rds.describe_db_clusters(
            DBClusterIdentifier=CLUSTER_ID
        )["DBClusters"][0]["Status"]
        print(f"  Status: {status}")
        if status == "available":
            break
        time.sleep(20)


def enable_pgvector(cluster_arn, secret_arn):
    print("Enabling pgvector extension...")
    data = boto3.client("rds-data", region_name=config.AWS_REGION)
    data.execute_statement(
        resourceArn = cluster_arn,
        secretArn   = secret_arn,
        database    = DB_NAME,
        sql         = "CREATE EXTENSION IF NOT EXISTS vector;"
    )
    print("  pgvector enabled.")


if __name__ == "__main__":
    secret_arn  = create_secret()
    cluster_arn = create_cluster()
    wait_for_cluster()
    enable_pgvector(cluster_arn, secret_arn)

    print("\n── Copy these into your .env ──────────────────────")
    print(f"AURORA_CLUSTER_ARN={cluster_arn}")
    print(f"AURORA_SECRET_ARN={secret_arn}")
    print("───────────────────────────────────────────────────")
