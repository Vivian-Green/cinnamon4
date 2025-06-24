import cinShared

async def test_command(message):
    await message.channel.send("yo")

def do_something(i):
    print(i)
    return i+1

async def do_while(message, i=0, range=50):
    i = do_something(i)
    if i < range:
        await do_while(message, i, range)

async def for_loop(message, i=0, range=50):
    if i < range:
        i = do_something(i)
        await for_loop(message, i, range)

async def ternary_do_while(message, i=0, range=50): (await ternary_do_while(message, do_something(i), range)) if do_something(i) < range else ()

def print_and_return(val):
    print(val)
    return val

async def ternary_fibonacci(message, a=1, b=1, i=0, maximum=50): (await ternary_fibonacci(message, print_and_return(b), a+b, i+1, maximum)) if i < maximum else "done"


def bind_commands():
     return {
         "test": test_command,
         "bullshit": ternary_do_while,
         "bullshit2": for_loop,
         "fibonacci": ternary_fibonacci
     }