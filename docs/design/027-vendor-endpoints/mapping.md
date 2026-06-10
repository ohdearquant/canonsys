# 027-vendor-endpoints - Vocabulary Mapping

## Package Mapping

| Aspect   | Value                                         |
| -------- | --------------------------------------------- |
| Package  | `core`                                        |
| Location | `hub/foundation/packages/core/` |
| Status   | Infrastructure (external integrations)        |

## Phrases

This is infrastructure for external integrations. No vocabulary phrases are directly implemented.

## Control Surfaces

| Surface                   | Description               | Key Integration                                                   |
| ------------------------- | ------------------------- | ----------------------------------------------------------------- |
| Vendor Integration        | Vendor Integration        | Endpoint resolution for external vendor calls                     |
| Integration System Link   | Integration System Link   | Vendor endpoint resolution for external system integrations       |
| Model Deployment Override | Model Deployment Override | LLM provider endpoints (Anthropic, OpenAI) via kron fallback      |
| AI Incident Disclosure    | AI Incident Disclosure    | Resend endpoint for notification delivery                         |
| Dataset External Publish  | Dataset External Publish  | S3 endpoint for external data storage                             |
| Threat Intel Disclosure   | Threat Intel Disclosure   | Vendor endpoints for threat intelligence sharing                  |

## Code Paths

### Primary Implementation

- `libs/canon/src/canon/utils/endpoints.py`
- `libs/canon/src/canon/services/vendor/`

### Registered Endpoints

| Provider     | Endpoint           | Location                                                        |
| ------------ | ------------------ | --------------------------------------------------------------- |
| `openai`     | `embeddings`       | `canon_services/embed/endpoints/openai.py`                      |
| `perplexity` | `chat/completions` | `canon_services/market/endpoints/perplexity.py`                 |
| `exa`        | `search`           | `canon_services/market/endpoints/exa.py`                        |
| `h1b`        | `salary`           | `canon_services/market/endpoints/h1b.py`                        |
| `aws`        | `s3`               | `libs/canon/src/canon/services/vendor/providers/storage/s3_endpoint.py`   |
| `resend`     | `emails`           | `hub/domains/governance/packages/notice/endpoints/resend_endpoint.py`       |
| `twilio`     | `messages`         | `hub/domains/governance/packages/notice/endpoints/twilio_endpoint.py`       |
| `apify`      | `actors`           | `libs/canon/src/canon/services/vendor/providers/market/apify/endpoint.py` |

## Dependencies

### Upstream

| Component | Purpose               |
| --------- | --------------------- |
| kron      | LLM endpoint fallback |

### Downstream

| Component      | Purpose                                |
| -------------- | -------------------------------------- |
| VendorService  | Uses `match_endpoint()` for resolution |
| EmbedService   | Uses OpenAI embedding endpoint         |
| MarketService  | Uses Perplexity, Exa, H1B endpoints    |
| NoticeService  | Uses Resend, Twilio for notifications  |
| StorageService | Uses S3 for file storage               |

## Verification

- **Last verified**: 2026-01-29
- **Design doc version**: 2.0.0
