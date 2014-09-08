# -*- coding:utf-8 -*-
"""Class python for Experiment serialization JSON"""


class AliasNodes(object):
    """An AliasNodes class"""
    _alias = 0  # static count of current alias number

    def __init__(self, nbnodes, properties):
        """
        {
            "alias":"1",
            "nbnodes":1,
            "properties":{
                "archi":"wsn430:cc2420",
                "site":"devlille",
                "mobile":False
            }
        }
        """
        AliasNodes._alias += 1
        self.alias = str(AliasNodes._alias)
        self.nbnodes = nbnodes
        self.properties = properties


class FirmwareAssociations(object):
    """A FirmwareAssociations class"""
    def __init__(self, firmwarename, nodes):
        self.firmwarename = firmwarename
        self.nodes = nodes

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.firmwarename == other.firmwarename
        else:
            return False


class ProfileAssociations(object):
    """A ProfileAssociations class"""
    def __init__(self, profilename, nodes):
        self.profilename = profilename
        self.nodes = nodes

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.profilename == other.profilename
        else:
            return False


class Experiment(object):
    """An Experiment class"""
    def __init__(self, name, duration, reservation):
        self.duration = duration
        self.reservation = reservation
        self.name = name

        self.type = None
        self.nodes = []
        self.firmwareassociations = None
        self.profileassociations = None

    def _set_type(self, exp_type):
        """ Set current experiment type.
        If type was already set and is different ValueError is raised
        """

        if self.type is not None and self.type != exp_type:
            raise ValueError(
                "Invalid experiment, should be only physical or only alias")
        self.type = exp_type

    def _safe_list_list_append(self, attribute, objs_list):
        l_l = getattr(self, attribute)
        l_l = l_l if l_l is not None else []

        if objs_list in l_l:
            old_values = set(l_l.pop(l_l.index(objs_list)))
            # list with all elements appearing only once
            objs_list = list(old_values.union(objs_list))

        l_l.append(objs_list)

        setattr(self, attribute, l_l)

    def add_experiment_dict(self, exp_dict):

        # register nodes in experiment
        nodes = exp_dict['nodes']
        {
            'physical': self.set_physical_nodes,
            'alias': self.set_alias_nodes,
        }[exp_dict['type']](nodes)

        # register profile, may be None
        self.set_profile_associations(exp_dict['profile'], nodes)

        # register firmware
        if exp_dict['firmware'] is not None:
            firmware = exp_dict['firmware']

            self.set_firmware_associations(firmware['name'], nodes)

    def set_firmware_associations(self, firmware_name, nodes):
        """Set firmware associations list"""
        # use alias number for AliasNodes
        _nodes = nodes.alias if self.type == 'alias' else nodes

        assoc = FirmwareAssociations(firmware_name, _nodes)
        self._safe_list_list_append('firmwareassociations', assoc)

    def set_profile_associations(self, profile_name, nodes):
        """Set profile associations list"""
        if profile_name is None:
            return

        # use alias number for AliasNodes
        _nodes = nodes.alias if self.type == 'alias' else nodes
        assoc = ProfileAssociations(profile_name, _nodes)
        self._safe_list_list_append('profileassociations', assoc)

    def set_physical_nodes(self, nodes_list):
        """Set physical nodes list """
        self._set_type('physical')

        self.nodes.extend(nodes_list)
        # Keep unique values and sorted
        self.nodes = sorted(list(set(self.nodes)), key=self._node_url_key)

    @staticmethod
    def _node_url_key(node_url):
        """
        >>> Experiment._node_url_key("m3-2.grenoble.iot-lab.info")
        ('grenoble', 'm3', 2)
        """
        _node, site = node_url.split('.')[0:2]
        node_type, num_str = _node.split('-')[0:2]
        return site, node_type, int(num_str)

    def set_alias_nodes(self, alias_nodes):
        """Set alias nodes list """
        self._set_type('alias')
        self.nodes.append(alias_nodes)
