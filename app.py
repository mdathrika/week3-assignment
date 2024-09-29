import json
from dotenv import load_dotenv
import os
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes, buy_ticket, get_reviews
load_dotenv()

print(os.getenv('TMDB_API_ACCESS_TOKEN'))
# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())

from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
 
client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}

SYSTEM_PROMPT = """\
You are assistant to find movie details. 
If user asks for movie related question, output function name and add to system context. Some functions require additional details(mentioned next to function name), ask user the details.

You can use the following functions:

get_now_playing_movies()
get_showtimes(): ** Ask user the movie title and the zipcode **
buy_ticket() ** Ask user the theater name, movie title and showtime **
get_reviews() ** Ask user the movie title for fetching reviews **

"""

@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@cl.on_message
@observe
async def on_message(message: cl.Message):
    print("Received Message:", message.content)
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})
    
    response_message = await generate_response(client, message_history, gen_kwargs)
    message_history.append({"role": "assistant", "content": response_message.content})
    print("Message History", message_history)
    print(response_message.content)
    if response_message.content.startswith("get_now_playing_movies") :
        nowplaying = get_now_playing_movies()
        print(nowplaying)
        message_history.append({"role": "system", "content": nowplaying})
        response_message = await generate_response(client, message_history, gen_kwargs)
        # print(response_message.content)
        message_history.append({"role": "assistant", "content": response_message.content})
        cl.user_session.set("message_history", message_history)
    elif response_message.content.startswith("get_showtimes") :
        message_history.append({"role": "system", "content": "Parse the movie title and zipcode from user message as JSON which can be recognize in Python. Do not include ```JSON start & end delimiter. \
                                JSON Example \"{\"title\": \"movie name\", \"zipcode\": \"12345\"}\""})
        response_message = await generate_response(client, message_history, gen_kwargs)
        message_history.append({"role": "assistant", "content": response_message.content})
        try:
            print(">>>>>>>>>SHOWtimes", response_message.content)
            parsed_data = json.loads(response_message.content)
            title = parsed_data.get('title')
            zipcode = parsed_data.get('zipcode')
            showtimes = get_showtimes(title, zipcode)
            message_history.append({"role": "system", "content": showtimes})
            response_message = await generate_response(client, message_history, gen_kwargs)
            message_history.append({"role": "assistant", "content": response_message.content})
        except json.JSONDecodeError:
            error_message = "Failed to parse movie title and zipcode. Please provide the details in the format: {'title': 'movie name', 'zipcode': '12345'}"
            message_history.append({"role": "system", "content": error_message})
            response_message = await generate_response(client, message_history, gen_kwargs)
            message_history.append({"role": "assistant", "content": response_message.content})
        cl.user_session.set("message_history", message_history)
    elif response_message.content.startswith("buy_ticket") :
        message_history.append({"role": "system", "content": "Parse the theater name, movie title and show time from user message as JSON which can be recognize in Python. Example \"{\"theater\": \"theater name\", \"title\": \"movie title\", \"showtime\": \"10:30pm\" }\""})
        response_message = await generate_response(client, message_history, gen_kwargs)
        message_history.append({"role": "assistant", "content": response_message.content})
        try:
            print(">>>>>>>>>Buy Tiekcts", response_message.content)
            parsed_data = json.loads(response_message.content)
            theater = parsed_data.get('theater')
            title = parsed_data.get('title')
            showtime = parsed_data.get('showtime')
            ticketBought = buy_ticket(theater, title, showtime)
            message_history.append({"role": "system", "content": ticketBought})
            response_message = await generate_response(client, message_history, gen_kwargs)
            message_history.append({"role": "assistant", "content": response_message.content})
        except json.JSONDecodeError:
            error_message = "Failed to parse theater, movie title and showtime. Please provide the details in the format: \"{\"theater\": \"theater name\", \"title\": \"movie title\", \"showtime\": \"10:30pm\" }\""
            message_history.append({"role": "system", "content": error_message})
            response_message = await generate_response(client, message_history, gen_kwargs)
            message_history.append({"role": "assistant", "content": response_message.content})
        cl.user_session.set("message_history", message_history)
    # elif response_message.content.startswith("get_reviews") :
    #     message = response_message.content.split("\n")

    print("Final Message History", message_history)
if __name__ == "__main__":
    cl.main()
