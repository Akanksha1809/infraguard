terraform {
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Local-only, zero-cost resources: no cloud account, credentials, or network access needed
# at apply time. This exists so the documented analyze-change workflow (see the README in
# this directory) is actually runnable by a reviewer with nothing but Terraform installed.

resource "random_pet" "suffix" {
  length = 2
}

resource "local_file" "config" {
  filename = "${path.module}/generated/app-config-${random_pet.suffix.id}.txt"
  content  = "app config for ${random_pet.suffix.id}\n"
}

resource "local_file" "readme" {
  filename   = "${path.module}/generated/README-${random_pet.suffix.id}.txt"
  content    = "See app-config-${random_pet.suffix.id}.txt\n"
  depends_on = [local_file.config]
}
