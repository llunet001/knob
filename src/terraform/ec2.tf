locals {
  ami_id = "ami-localstack"
}

resource "aws_instance" "write" {
  ami           = local.ami_id
  instance_type = "t3.micro"

  provisioner "file" {
    source      = "../services/write_service.py"
    destination = "/home/ec2-user/app.py"
  }

  provisioner "remote-exec" {
    inline = [
      "pip install flask boto3 pycryptodome",
      "python /home/ec2-user/app.py &"
    ]
  }
}

resource "aws_instance" "read" {
  ami           = local.ami_id
  instance_type = "t3.micro"

  provisioner "file" {
    source      = "../services/read_service.py"
    destination = "/home/ec2-user/app.py"
  }

  provisioner "remote-exec" {
    inline = [
      "pip install flask boto3 pycryptodome",
      "python /home/ec2-user/app.py &"
    ]
  }
}

resource "aws_instance" "reencrypt" {
  ami           = local.ami_id
  instance_type = "t3.micro"

  provisioner "file" {
    source      = "../services/reencrypt_service.py"
    destination = "/home/ec2-user/app.py"
  }

  provisioner "remote-exec" {
    inline = [
      "pip install flask boto3 pycryptodome",
      "python /home/ec2-user/app.py &"
    ]
  }
}
