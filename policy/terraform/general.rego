package terraform.general

deny[msg] {
  input.resource_type == "aws_security_group_rule"
  input.change.after.cidr_blocks[_] == "0.0.0.0/0"
  msg = sprintf("security group rule %s allows 0.0.0.0/0", [input.address])
}

deny[msg] {
  input.change.after.tags.Owner == ""
  msg = sprintf("resource %s missing Owner tag", [input.address])
}

deny[msg] {
  input.change.after.tags.CostCenter == ""
  msg = sprintf("resource %s missing CostCenter tag", [input.address])
}
