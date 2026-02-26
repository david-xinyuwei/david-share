import os  
import getpass  
from transformers import AutoConfig  
  
def main():  
    # Adding a nicely formatted banner  
    print("\n" + "#" * 70)  
    print("#" + " " * 68 + "#")  
    print("#{:^68}#".format("Model Memory Consumption Calculator V1.0"))  
    print("#{:^68}#".format("https://github.com/xinyuwei-david/david-share.git"))  
    print("#" + " " * 68 + "#")  
    print("#" * 70 + "\n")  
  
    print("Note: Ensure that your environment has internet access to Hugging Face and that you have set your Hugging Face API token.\n")  
  
    # Input model name  
    model_name = input("Enter the model name from Hugging Face: ")  
  
    if model_name:  
        try:  
            # Set Hugging Face API token if available  
            hf_token = os.getenv('HF_API_TOKEN')  
            if not hf_token:  
                hf_token = getpass.getpass("Enter your Hugging Face API token: ")  
                if hf_token:  
                    os.environ['HF_API_TOKEN'] = hf_token  
  
            if not hf_token:  
                print("Hugging Face API token is required. Please set it in the environment variable 'HF_API_TOKEN' or enter it above.")  
                return  
  
            # Load model configuration from Hugging Face  
            print('\nLoading model configuration...')  
            model_config = AutoConfig.from_pretrained(model_name, use_auth_token=hf_token)  
  
            hidden_layers = model_config.num_hidden_layers  
            hidden_size = model_config.hidden_size  
            attention_heads = model_config.num_attention_heads  
            kv_heads = getattr(model_config, "num_key_value_heads", None)  
  
            # Determine if the model uses GQA  
            uses_gqa = False  
            if kv_heads is not None and kv_heads != attention_heads and kv_heads > 0:  
                uses_gqa = True  
            else:  
                kv_heads = 0  # Ensure kv_heads is set to 0 if not used  
  
            # Display model parameters  
            print("\n--- Model Parameters ---")  
            print(f"Model Name: {model_name}")  
            print(f"Number of Hidden Layers (L): {hidden_layers}")  
            print(f"Hidden Size (h): {hidden_size}")  
            print(f"Number of Attention Heads (a): {attention_heads}")  
            if uses_gqa:  
                print(f"Number of Key-Value Heads (g): {kv_heads}")  
                print("The model uses Grouped Query Attention (GQA).")  
            else:  
                print("The model does not use Grouped Query Attention (GQA).")  
  
            # Input adjustable parameters  
            print("\n--- Adjustable Parameters ---")  
  
            # Prompt user for inputs  
            while True:  
                try:  
                    nb_billion_parameters = float(input("Number of parameters in the model (n) (in billions) (**Please enter this manually**): "))  
                    break  
                except ValueError:  
                    print("Please enter a valid number.")  
  
            while True:  
                try:  
                    bitwidth_model_input = input("Bitwidth of the model's parameters (p) (in bits) [Default 16]: ")  
                    bitwidth_model = int(bitwidth_model_input) if bitwidth_model_input.strip() != "" else 16  
                    break  
                except ValueError:  
                    print("Please enter a valid integer.")  
  
            while True:  
                try:  
                    seqlen = int(input("Sequence length (s) (**Please enter this manually**): "))  
                    break  
                except ValueError:  
                    print("Please enter a valid integer.")  
  
            while True:  
                try:  
                    batch_size_input = input("Batch size (b) (**Please enter this manually**) [Default 1]: ")  
                    batch_size = int(batch_size_input) if batch_size_input.strip() != "" else 1  
                    break  
                except ValueError:  
                    print("Please enter a valid integer.")  
  
            while True:  
                Flash_Attention_input = input("Use FlashAttention? [Y/n] (Default Y): ").strip().lower()  
                if Flash_Attention_input in ['y', 'yes', '']:  
                    Flash_Attention = True  
                    break  
                elif Flash_Attention_input in ['n', 'no']:  
                    Flash_Attention = False  
                    break  
                else:  
                    print("Please enter 'Y' or 'N'.")  
  
            while True:  
                Use_KV_Cache_input = input("Use KV Cache? [Y/n] (Default Y): ").strip().lower()  
                if Use_KV_Cache_input in ['y', 'yes', '']:  
                    Use_KV_Cache = True  
                    break  
                elif Use_KV_Cache_input in ['n', 'no']:  
                    Use_KV_Cache = False  
                    break  
                else:  
                    print("Please enter 'Y' or 'N'.")  
  
            # Now validate inputs  
            if seqlen == 0 or nb_billion_parameters == 0.0:  
                print("Please enter valid values for 'Number of parameters in the model (n) (in billions)' and 'Sequence length (s)'.")  
                return  
  
            tile_size = 128 if Flash_Attention else None  
            kv_cache_length = seqlen if Use_KV_Cache else 0  
  
            # Define computation functions  
            def estimate_consumption_inference():  
                return round((32 * seqlen * batch_size * hidden_size + 4 * attention_heads * seqlen * seqlen * batch_size) * 2 / (1000 ** 3), 2)  
  
            def estimate_consumption_inference_gqa():  
                return round((28 * seqlen * batch_size * hidden_size + ((2 * kv_heads) / attention_heads) * seqlen * batch_size * hidden_size + 4 * kv_heads * seqlen * seqlen * batch_size) * 2 / (1000 ** 3), 2)  
  
            def estimate_consumption_inference_FA():  
                return round((32 * seqlen * batch_size * hidden_size + 4 * tile_size * seqlen * batch_size) * 2 / (1000 ** 3), 2)  
  
            def kv_cache():  
                return round(2 * hidden_layers * seqlen * batch_size * hidden_size * 2 / (1000 ** 3), 2)  
  
            def kv_cache_gqa():  
                return round(2 * hidden_layers * seqlen * batch_size * (hidden_size / kv_heads) * 2 / (1000 ** 3), 2)  
  
            def estimate_model_size():  
                return round(nb_billion_parameters * (bitwidth_model / 8) * (1000 ** 3) / (1000 ** 3), 2)  
  
            # Calculate memory consumption  
            activation_consumption_inference = estimate_consumption_inference()  
            activation_consumption_inference_gqa = estimate_consumption_inference_gqa() if uses_gqa else None  
            activation_consumption_inference_FA = estimate_consumption_inference_FA() if Flash_Attention else None  
            model_consumption = estimate_model_size()  
  
            # Display calculation results  
            print("\n--- Memory Consumption Results ---")  
            print(f"Memory consumption of the model: {model_consumption} GB")  
  
            print(f"Memory consumption of vanilla inference: {activation_consumption_inference} GB")  
  
            if uses_gqa:  
                print(f"Memory consumption of inference with GQA: {activation_consumption_inference_gqa} GB")  
  
            if Flash_Attention:  
                print(f"Memory consumption of inference with FlashAttention: {activation_consumption_inference_FA} GB")  
  
            if Use_KV_Cache:  
                if uses_gqa:  
                    kv_cache_cost = kv_cache_gqa()  
                    print(f"Memory consumption of the KV cache (with GQA): {kv_cache_cost} GB")  
                else:  
                    kv_cache_cost = kv_cache()  
                    print(f"Memory consumption of the KV cache: {kv_cache_cost} GB")  
            else:  
                kv_cache_cost = 0  
  
            if Flash_Attention:  
                total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference_FA, 2)  
            elif uses_gqa:  
                total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference_gqa, 2)  
            else:  
                total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference, 2)  
  
            print(f"\nTotal Memory consumption (given the selected configuration): {total_memory} GB")  
  
        except Exception as e:  
            print(f"Could not load model configuration. Please check if the model name is correct and your Hugging Face API token is valid.\nError: {e}")  
  
if __name__ == "__main__":  
    main()  
