import os  
import streamlit as st  
from transformers import AutoConfig  
  
def main():  
    st.title("Model Memory Consumption Calculator")  
  
    st.write("**Note:** Ensure that your environment has internet access to Hugging Face and that you have set your Hugging Face API token.")  
  
    # Input model name  
    model_name = st.text_input("Enter the model name from Hugging Face:")  
  
    if model_name:  
        try:  
            # Set Hugging Face API token if available  
            hf_token = os.getenv('HF_API_TOKEN')  
            if not hf_token:  
                hf_token = st.text_input("Enter your Hugging Face API token:", type="password")  
                if hf_token:  
                    os.environ['HF_API_TOKEN'] = hf_token  
  
            if not hf_token:  
                st.error("Hugging Face API token is required. Please set it in the environment variable 'HF_API_TOKEN' or enter it above.")  
                return  
  
            # Load model configuration from Hugging Face  
            with st.spinner('Loading model configuration...'):  
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
            st.subheader("Model Parameters:")  
            st.write(f"**Model Name:** {model_name}")  
            st.write(f"**Number of Hidden Layers (L):** {hidden_layers}")  
            st.write(f"**Hidden Size (h):** {hidden_size}")  
            st.write(f"**Number of Attention Heads (a):** {attention_heads}")  
            if uses_gqa:  
                st.write(f"**Number of Key-Value Heads (g):** {kv_heads}")  
                st.write("**The model uses Grouped Query Attention (GQA).**")  
            else:  
                st.write("**The model does not use Grouped Query Attention (GQA).**")  
  
            # Input adjustable parameters  
            st.subheader("Adjustable Parameters:")  
            # Use a form to allow users to adjust parameters and submit  
            with st.form(key='adjustable_parameters_form'):  
                nb_billion_parameters = st.number_input(  
                    "Number of parameters in the model (n) (in billions) (**Please enter this manually**)",  
                    value=0.0  
                )  
                bitwidth_model = st.number_input("Bitwidth of the model's parameters (p) (in bits)", value=16, step=1)  
                seqlen = st.number_input(  
                    "Sequence length (s) (**Please enter this manually**)",  
                    value=0, step=1  
                )  
                batch_size = st.number_input(  
                    "Batch size (b) (**Please enter this manually**)",  
                    value=1, step=1  
                )  
                Flash_Attention = st.checkbox("Use FlashAttention", value=True)  
                Use_KV_Cache = st.checkbox("Use KV Cache", value=True)  
  
                submit_button = st.form_submit_button(label='Submit')  
  
            if submit_button:  
                if seqlen == 0 or nb_billion_parameters == 0.0:  
                    st.error("Please enter valid values for 'Number of parameters in the model (n) (in billions)' and 'Sequence length (s)'.")  
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
                activation_consumption_inference_gqa = estimate_consumption_inference_gqa()  
                activation_consumption_inference_FA = estimate_consumption_inference_FA()  
                model_consumption = estimate_model_size()  
  
                # Display calculation results  
                st.subheader("Memory Consumption Results:")  
                st.write(f"**Memory consumption of the model:** {model_consumption} GB")  
  
                st.write(f"**Memory consumption of vanilla inference:** {activation_consumption_inference} GB")  
  
                if uses_gqa:  
                    st.write(f"**Memory consumption of inference with GQA:** {activation_consumption_inference_gqa} GB")  
  
                if Flash_Attention:  
                    st.write(f"**Memory consumption of inference with FlashAttention:** {activation_consumption_inference_FA} GB")  
  
                if Use_KV_Cache:  
                    if uses_gqa:  
                        kv_cache_cost = kv_cache_gqa()  
                        st.write(f"**Memory consumption of the KV cache (with GQA):** {kv_cache_cost} GB")  
                    else:  
                        kv_cache_cost = kv_cache()  
                        st.write(f"**Memory consumption of the KV cache:** {kv_cache_cost} GB")  
                else:  
                    kv_cache_cost = 0  
  
                if Flash_Attention:  
                    total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference_FA, 2)  
                elif uses_gqa:  
                    total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference_gqa, 2)  
                else:  
                    total_memory = round(model_consumption + kv_cache_cost + activation_consumption_inference, 2)  
  
                st.write(f"\n**Total Memory consumption (given the selected configuration):** {total_memory} GB")  
  
        except Exception as e:  
            st.error(f"Could not load model configuration. Please check if the model name is correct and your Hugging Face API token is valid.\nError: {e}")  
  
if __name__ == "__main__":  
    main()  
