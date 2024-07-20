import bcrypt



def hash(password : str):
    encoded_pass = password.encode("utf-8")
    hashed_bytes = bcrypt.hashpw(encoded_pass, bcrypt.gensalt())
    
    return hashed_bytes.decode('utf-8')


def check(password : str, hash : str):
    encoded_pass = password.encode("utf-8")
    encoded_hash = hash.encode("utf-8")

    return bcrypt.checkpw(encoded_pass, encoded_hash)