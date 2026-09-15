from src.production_model.runtime import hydrate_model
def test_hydrate_registered_model():
 rec={"model":{"feature_names":["intercept","op:K/1000","wale_spacing_mm","course_spacing_mm","yarn_diameter_mm"],
 "coefficients":[0,1,0,0,0],"operation_ids":["K"],"rmse_m":1,"mae_m":1,"mean_error_m":0,"residual_std_m":1,
 "n_samples":10,"ridge_lambda":1e-6,"domains":{"wale_spacing_mm":[4,6],"course_spacing_mm":[3,5],"yarn_diameter_mm":[1,2],"operation_ids":["K"]}}}
 m,s=hydrate_model(rec);assert m.n_samples==10 and s.operation_ids==("K",)
