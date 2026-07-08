# Verify with mock provider and save JSON report
miv verify \
  --provider mock \
  --model mock-model \
  --expected-identity claude \
  --mode quick \
  --format json \
  --output report.json
