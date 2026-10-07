# Deployment Documentation

## Docker

```bash
docker-compose up --db
```

## Production Checklist

- [ ] Set `APP_ENV=production`
- [ ] Set `DRY_RUN=false`
- [ ] Configure TiDB Cloud connection
- [ ] Set strong `SECRET_KEY`
- [ ] Configure LLM provider API keys
- [ ] Set up notification providers (SMTP, Twilio, WhatsApp)
- [ ] Run database migrations
- [ ] Set up SSL/TLS
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerting
- [ ] Enable audit logging

## Environment Variables

See `.env.example` for all configuration options.

## Scaling

- API: Horizontal scaling with load balancer
- Worker: Separate container for reminders/notifications
- Dashboard: Single instance (admin only)
- Database: TiDB Cloud auto-scaling
