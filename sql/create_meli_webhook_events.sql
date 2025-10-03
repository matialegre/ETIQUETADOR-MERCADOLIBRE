CREATE TABLE dbo.meli_webhook_events (
  id INT IDENTITY(1,1) PRIMARY KEY,
  received_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  topic NVARCHAR(50) NOT NULL,
  resource NVARCHAR(300) NULL,
  resource_id BIGINT NULL,
  user_id BIGINT NULL,
  application_id BIGINT NULL,
  status NVARCHAR(20) NOT NULL DEFAULT 'pending',
  attempts INT NOT NULL DEFAULT 0,
  processed_at DATETIME2 NULL,
  error NVARCHAR(MAX) NULL,
  payload_json NVARCHAR(MAX) NOT NULL,
  remote_ip NVARCHAR(64) NULL,
  request_headers_json NVARCHAR(MAX) NULL
);

CREATE INDEX IX_meli_webhook_events_status ON dbo.meli_webhook_events(status, received_at);
CREATE INDEX IX_meli_webhook_events_resource_id ON dbo.meli_webhook_events(resource_id);
