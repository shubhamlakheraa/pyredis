from pyredis.encoder import encode_simple_string, encode_bulk

def handle_ping(args: list[bytes]) -> bytes :
    if len(args) == 1:
        return encode_simple_string("PONG")
    return encode_bulk(args[1])

def handle_echo(args: list[bytes]) -> bytes :
    return encode_bulk(args[1])



