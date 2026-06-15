from db import get_db_collection, query_collection, generate_context
from llm import llm_invoke, prepare_chat_prompt


COLLECTION_NAME = "my_project"
collection = get_db_collection(COLLECTION_NAME)


while True:

    query_text = input(
        "Ask anything about Automatic Medicine Vending Machine project. (Enter q to quit) :\n"
    )
    if query_text == "q":
        print("Quitting...\n\n")
        break

    query_result = query_collection(collection, query_text)
 
    context = generate_context(query_result)

    prompt = prepare_chat_prompt(context, query_text)

    result = llm_invoke(prompt)

    print(result, "\n\n")
