# =============================================================================
# TERRAFORM CONFIGURATION - Auto-generated from Workflow Canvas
# Generated: 2026-03-28T10:49:11.927Z
# Nodes: 3 | Connections: 3
# =============================================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# VARIABLES
# =============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# =============================================================================
# RESOURCES
# =============================================================================

resource "aws_api_gateway_rest_api" "api_gateway_2" {

  tags = {
    Name        = "api_gateway_2"
    Environment = "development"
    ManagedBy   = "terraform"
    CreatedBy   = "workflow-canvas"
  }

  depends_on = [
    aws_sns_topic.sns_3,
  ]
}

resource "aws_sns_topic" "sns_3" {

  tags = {
    Name        = "sns_3"
    Environment = "development"
    ManagedBy   = "terraform"
    CreatedBy   = "workflow-canvas"
  }

  depends_on = [
    aws_api_gateway_rest_api.api_gateway_2,
  ]
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "api_gateway_2_id" {
  description = "ID of api_gateway_2"
  value       = aws_api_gateway_rest_api.api_gateway_2.id
}

output "sns_3_id" {
  description = "ID of sns_3"
  value       = aws_sns_topic.sns_3.id
}
