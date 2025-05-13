MERGE (c:Currency {code: $code})
SET c.description = $description
