terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "finflow_data" {
  bucket = "finflow-data-sxvarma"

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}

# IAM role for Glue crawler
resource "aws_iam_role" "glue_role" {
  name = "finflow-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "glue.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy_attachment" "glue_s3" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Glue catalog database
resource "aws_glue_catalog_database" "bronze" {
  name        = "finflow_bronze"
  description = "Raw bronze layer for FinFlow"
}

# Glue crawler
resource "aws_glue_crawler" "market_data" {
  name          = "finflow-market-data-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.bronze.name

  s3_target {
    path = "s3://finflow-data-sxvarma/bronze/market_data/"
  }

  schedule = "cron(0 6 * * ? *)"

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}
# IAM role for Redshift Serverless
resource "aws_iam_role" "redshift_role" {
  name = "finflow-redshift-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "redshift.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}

resource "aws_iam_role_policy_attachment" "redshift_s3" {
  role       = aws_iam_role.redshift_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "redshift_glue" {
  role       = aws_iam_role.redshift_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}

# Redshift Serverless
resource "aws_redshiftserverless_namespace" "finflow" {
  namespace_name      = "finflow"
  admin_username      = "admin"
  admin_user_password = "FinFlow2026!#"
  db_name             = "finflow_db"
  iam_roles           = [aws_iam_role.redshift_role.arn]

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}

resource "aws_redshiftserverless_workgroup" "finflow" {
  namespace_name      = aws_redshiftserverless_namespace.finflow.namespace_name
  workgroup_name      = "finflow-workgroup"
  base_capacity       = 8
  publicly_accessible = true

  tags = {
    Project     = "finflow"
    Environment = "dev"
  }
}