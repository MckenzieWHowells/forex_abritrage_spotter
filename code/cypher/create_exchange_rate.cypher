MATCH (from:Currency {code: $from_code})
MATCH (to:Currency {code: $to_code})
MERGE (from)-[r:EXCHANGE_TO {date: $date}]->(to)
SET r.rate = $rate
