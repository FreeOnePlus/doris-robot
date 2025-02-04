def validate_config(config):
    required_providers = set()
    # 自动收集所有service使用的provider
    for service in config["model_config"]["services"].values():
        required_providers.add(service["provider"])
    
    # 验证必要配置
    for provider in required_providers:
        if provider not in config["model_config"]["providers"]:
            raise ValueError(f"缺少{provider}的提供商配置")
        if "api_key" not in config["model_config"]["providers"][provider]:
            raise ValueError(f"{provider}缺少api_key配置") 