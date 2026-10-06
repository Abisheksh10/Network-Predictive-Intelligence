tools = [
    {
        "name": "get_pipeline_status",
        "description": "Check the operational pipeline health and data trustworthiness before stating facts. Returns whether the underlying analytics layer is healthy, row audits, and AS_OF timestamp.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_network_summary",
        "description": "Get network-wide operational activity summaries. Leave as_of null to use latest available reporting window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": {
                    "type": "string",
                    "description": "Optional ISO timestamp cutoff (e.g., 2013-11-07T23:00:00)."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_hotspots",
        "description": "Get ranked operational hotspots and elevated cells across the Milan network.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top hotspots to return (default 10)"
                },
                "as_of": {
                    "type": "string",
                    "description": "Optional ISO timestamp cutoff."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_grid_activity",
        "description": "Get time-series activity for a specific grid cell. Omit date/hour/as_of to retrieve latest records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {
                    "type": "integer",
                    "description": "Milan grid cell ID (1 to 10000)"
                },
                "as_of": {
                    "type": "string",
                    "description": "Optional ISO timestamp cutoff."
                }
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_grid_features",
        "description": "Get calculated ML features (average activity, growth, peak ratio, variability, internet share) for a specific grid.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {
                    "type": "integer",
                    "description": "Milan grid cell ID (1 to 10000)"
                },
                "as_of": {
                    "type": "string",
                    "description": "Optional ISO timestamp cutoff."
                }
            },
            "required": ["grid_id"]
        }
    },
    {
        "name": "get_anomaly_score",
        "description": "Get statistical anomaly z-score and direction for a grid cell at a specific timestamp.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {
                    "type": "integer",
                    "description": "Milan grid cell ID (1 to 10000)"
                },
                "timestamp": {
                    "type": "string",
                    "description": "ISO timestamp from grid activity (e.g., 2013-11-07T00:00:00)."
                }
            },
            "required": ["grid_id", "timestamp"]
        }
    },
    {
        "name": "get_grid_location",
        "description": "Get spatial centroid coordinates (latitude, longitude) and polygon reference for a grid cell.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {
                    "type": "integer",
                    "description": "Milan grid cell ID (1 to 10000)"
                }
            },
            "required": ["grid_id"]
        }
    }
]