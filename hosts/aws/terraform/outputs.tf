output "instance_id" {
  description = "The EC2 instance ID fulfilled by the spot request."
  value       = aws_spot_instance_request.this.spot_instance_id
}

output "spot_request_id" {
  description = "The spot request ID. Useful for AWS console lookups."
  value       = aws_spot_instance_request.this.id
}

output "public_ip" {
  description = "Public IPv4 address of the instance."
  value       = aws_spot_instance_request.this.public_ip
}

output "public_dns" {
  description = "Public DNS name of the instance."
  value       = aws_spot_instance_request.this.public_dns
}

output "availability_zone" {
  description = "AZ the instance was placed in."
  value       = local.target_az
}

output "ami_id" {
  description = "AMI the instance was launched from."
  value       = data.aws_ami.dlami.id
}

output "ami_name" {
  description = "Human-readable AMI name."
  value       = data.aws_ami.dlami.name
}

output "ssh_cidr" {
  description = "CIDR allowed to SSH. If auto-detected, this was derived from api.ipify.org at plan time."
  value       = local.ssh_cidr
}

output "ssh_command" {
  description = "Copy-paste SSH command. Replace the key path as needed."
  value       = "ssh -i ~/.ssh/aws/${var.key_pair_name}.pem ubuntu@${aws_spot_instance_request.this.public_ip}"
}

output "destroy_hint" {
  description = "How to tear this all down."
  value       = "cd hosts/aws/terraform && terraform destroy"
}
