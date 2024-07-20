class TokenError(Exception):
    pass

class FailedToJoin(TokenError):
    pass

class InvalidToken(TokenError):
    pass

class LockedToken(TokenError):
    pass

class FailedToBoost(TokenError):
    pass

class OutOfBoosts(TokenError):
    pass

class OutOfStock(TokenError):
    pass

class RequestFailed(Exception):
    pass

class DatabaseError(Exception):
    pass

class QuarantinedToken(TokenError):
    pass

class SpammerToken(TokenError):
    pass

class RetryTimeout(Exception):
    """
    Request has failed more than the `self.max_retries` value.
    """
    def __init__(self, message:str, errors:list) -> None:
        self.errors = errors
        self.message = message
    
    def __str__(self) -> str:
        return self.message

class BotOauthError(Exception):
    pass

class BotNoPerms(Exception):
    pass
