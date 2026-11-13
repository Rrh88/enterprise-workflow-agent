# Architecture (draft, filled in as phases complete)
upload -> classify -> extract (OCR + vision LLM) -> validate (rules) -> route -> [auto-approve | human review | reject] -> action
Open design items: idempotency key per step, retry policy table, dead-letter queue, failure-mode table,
per-field confidence thresholds, prompt caching + file-hash exact cache, audit log.
