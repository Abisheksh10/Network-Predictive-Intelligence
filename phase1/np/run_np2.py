from usage_processor import UsageProcessor


processor = UsageProcessor(
    file_path="../data/landing/sms-call-internet-mi-2013-11-01.csv"
)


processor.load_data()

processor.clean_data()

processor.derive_time_features()

processor.aggregate_to_grid_time()

processor.derive_activity_features()

processor.compute_kpis()

processor.export_summary(
    "../data/outputs"
)