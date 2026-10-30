# Load balancer of US-27 (T-27.3): one internet-facing ALB in front of every API, with one target group
# per service and routing by path prefix:
#
#   http://<alb>/consumption/...     -> api-customer-consumption (8001)
#   http://<alb>/control-center/...  -> api-control-center       (8002)
#   http://<alb>/inventory/...       -> api-network-inventory    (8003)
#   http://<alb>/f5/...              -> api-transformer-metering (8005)
#
# The prefix is not removed: each API runs with ROOT_PATH=<prefix> and serves both <prefix>/x and /x.
# HTTP only: the pilot has no domain, so there is no TLS certificate (noted in ADR-011 consequences).

resource "aws_lb" "this" {
  name               = var.name
  internal           = false
  load_balancer_type = "application"
  subnets            = var.subnet_ids
  security_groups    = [var.security_group_id]

  drop_invalid_header_fields = true
  idle_timeout               = 60

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_lb_target_group" "this" {
  for_each = var.routes

  # Name max 32 characters: voltiagrid-dev-api-customer-consumption would be too long.
  name        = substr("${var.name}-${each.value.short_name}", 0, 32)
  port        = each.value.port
  protocol    = "HTTP"
  target_type = "ip" # Fargate tasks register by IP
  vpc_id      = var.vpc_id

  # Tasks finish their in-flight requests within 30 s when replaced (default is 300 s).
  deregistration_delay = 30

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = merge(var.tags, { Name = each.key })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  # Any path that is not an API prefix gets a JSON 404 in the same format as the APIs.
  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({ detail = "Not found. Use /consumption, /control-center, /inventory or /f5." })
      status_code  = "404"
    }
  }

  tags = var.tags
}

resource "aws_lb_listener_rule" "route" {
  for_each = var.routes

  listener_arn = aws_lb_listener.http.arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.key].arn
  }

  condition {
    path_pattern {
      values = [each.value.path_prefix, "${each.value.path_prefix}/*"]
    }
  }

  tags = merge(var.tags, { Name = each.key })
}
