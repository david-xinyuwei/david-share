from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate


llm = Ollama(
    model="phi3",
    keep_alive=-1,
    format="json"
)


def prepare_chat_prompt(context:str, prompt:str):
    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer "
        "the question. If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the "
        "answer concise."
        "\n\n"
        "{context}"
    ).format(context=context)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    final_prompt = prompt.format(input=prompt)
    return final_prompt


def llm_invoke(prompt:str):
    return llm.invoke(prompt)