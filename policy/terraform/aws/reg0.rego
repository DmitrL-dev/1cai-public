package terraform.aws

deny[msg] {
  input.resource_type == "aws_s3_bucket"
  input.change.after.acl == "public-read"
  msg = sprintf("S3 bucket %s must not be public", [input.address])
}

deny[msg] {
  input.resource_type == "aws_db_instance"
  input.change.after.publicly_accessible == true
  msg = sprintf("DB instance %s is publicly accessible", [input.address])
}
