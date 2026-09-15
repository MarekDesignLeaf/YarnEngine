from src.multiyarn.engine import calculate_multiyarn
def test_routes_yarn_and_explicit_float():
 p=[{"yarn_id":"A","op":"SC","n":100},{"yarn_id":"B","op":"SC","n":50,"float_length_m":2}]
 def pred(y,ops):return {"recommended_length_m":10 if y=="A" else 5}
 r=calculate_multiyarn(p,{"A":{},"B":{}},pred)
 assert r["per_yarn"]["A"]["total_length_m"]==10 and r["per_yarn"]["B"]["total_length_m"]==7 and r["total_length_m"]==17
