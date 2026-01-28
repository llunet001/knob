resource "aws_s3_bucket" "image_bank" {
  bucket        = "image-bank"
  force_destroy = true
}
