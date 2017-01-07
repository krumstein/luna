__version__ = '0.0.1a'
__all__ = ['cluster', 'osimage', 'bmcsetup', 'node', 'switch', 'network', 'tracker', 'manager', 'utils']
__author__ = 'Dmitry Chirikov'

'''
Written by Dmitry Chirikov <dmitry@chirikov.ru>
This file is part of Luna, cluster provisioning tool
https://github.com/dchirikov/luna

This file is part of Luna.

Luna is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Luna is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Luna.  If not, see <http://www.gnu.org/licenses/>.

'''

from luna.config import *
import pymongo
from cluster import Cluster
from osimage import OsImage
from bmcsetup import BMCSetup
from node import Node, Group
from switch import Switch, MacUpdater
from network import Network
from tracker import *
from manager import Manager
from otherdev import OtherDev
import utils

def list(collection):
    import logging
    logging.basicConfig(level=logging.INFO)
#    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    try:
        mongo_client = pymongo.MongoClient(utils.helpers.get_con_options())
    except:
        logger.error("Unable to connect to MongoDB.")
        raise RuntimeError
    logger.debug("Connection to MongoDB was successful.")
    mongo_db = mongo_client[db_name]
    mongo_collection = mongo_db[collection]
    ret = []
    for doc in mongo_collection.find({}):
        try:
            ret.extend([doc['name']])
        except:
            ret.extend([doc['_id']])
    ret.sort()
    return [str(elem) for elem in ret]
