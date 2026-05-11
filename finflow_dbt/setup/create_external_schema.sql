CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum_bronze
FROM DATA CATALOG
DATABASE 'finflow_bronze'
IAM_ROLE 'arn:aws:iam::639163294946:role/finflow-redshift-role'
REGION 'us-east-1';