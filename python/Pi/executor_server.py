
""" Implementation of my GRPC message.Executor server. """

from concurrent import futures

import grpc
from google.protobuf.json_format import MessageToJson, MessageToDict

import message_pb2
import message_pb2_grpc
from .light import message_handler
from .message import SceneMessage, AdministrativeMessage



LOGGER_NAME = 'log/gRPC_Server.log'
LOG_LOCATION = 'server_logger'

ID = 'Id'
FUNCTION_CALL = 'functionCall'
VALUE = 'value'


class Executor(message_pb2_grpc.ExecutorServicer):
    def configure_logger() -> logging.Logger:
        logger = logging.getLogger(LOGGER_NAME)
        handler = logging.FileHandler(LOG_LOCATION)

        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        return logger

    def ApplyChange(request, context):
        # Hit the message_handler function:
        #   (also move paint_static_colors into animation_handler and get rid of animated bool)        
        logger = configure_logger()
        logger.debug('in ApplyChange(); request: {}'.format(request))
        # Use Google's protobuf -> Dict deserializer: 
        message = MessageToDict(request)
        # Then convert the Dict to a Python Object as one of the two types I've defined in message.py:
        message_object = ConstructMessage(message)
        logger.debug('message object constructed from Dict: {}'.format(message_object))
        # Take the object & pass it to the message_handler in light.py:
        message_handler(message_object)
        return message_pb2.ChangeReply(message='success')

    
    def ConstructMessage(message):
        # SceneMessages have Ids; AdministrativeMessages do not. Cast appropriately via duck typing: 
        if (message[ID]):
            message_object = SceneMessage(message)
        else:
            message_object = AdministrativeMessage(message[FUNCTION_CALL], message[VALUE])
        
        return message_object



def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_ExecutorServicer_to_server(Executor(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info('Started server.')
    server.wait_for_termination()


# Unused at the moment - ExecutorServer is served by light.py.
# if __name__ == '__main__':
#     logging.basicConfig()
#     serve()
