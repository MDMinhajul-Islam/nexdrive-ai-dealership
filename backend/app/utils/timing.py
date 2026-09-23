import contextvars

# Store timing data inside a mutable dict so it is preserved across thread boundaries
timing_data_ctx = contextvars.ContextVar("timing_data", default={"normalization": 0.0, "db": 0.0, "response_build": 0.0})
