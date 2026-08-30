CREATE TABLE IF NOT EXISTS public.financing_rules (
    rule_id TEXT PRIMARY KEY, credit_tier TEXT NOT NULL UNIQUE,
    min_score SMALLINT NOT NULL, max_score SMALLINT NOT NULL,
    apr_36 NUMERIC(5,2) NOT NULL, apr_48 NUMERIC(5,2) NOT NULL,
    apr_60 NUMERIC(5,2) NOT NULL, apr_72 NUMERIC(5,2) NOT NULL,
    CHECK (min_score BETWEEN 300 AND 850 AND max_score BETWEEN min_score AND 850)
);
