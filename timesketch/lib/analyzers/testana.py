"""Sketch analyzer plugin for testana."""
from __future__ import unicode_literals

from timesketch.lib.analyzers import interface
from timesketch.lib.analyzers import manager

class Info(object):
    def __init__(self):
        self.descToTS = dict()
        self.dirty = False
        self.name = None

class TestanaSketchPlugin(interface.BaseSketchAnalyzer):
    """Sketch analyzer for Testana."""

    NAME = 'testana'

    DEPENDENCIES = frozenset(['timestomp'])

    CDESC = 'Creation Time'
    ADESC = 'Last Access Time'
    MODDESC = 'Content Modification Time'
    METADESC = 'Metadata Modification Time'
    resolution = 1000000

    def __init__(self, index_name, sketch_id):
        """Initialize The Sketch Analyzer.

        Args:
            index_name: Elasticsearch index name
            sketch_id: Sketch ID
        """
        self.index_name = index_name
        super(TestanaSketchPlugin, self).__init__(index_name, sketch_id)

    def insert(self, m, file_ref, name, timestamp_desc, timestamp, is_dirty):
        """return if file is dirty, number of types of timestamps"""
        f = m.get(file_ref)
        if not f:
            f = Info()
            m[file_ref] = f
        f.dirty = f.dirty or is_dirty
        f.name = name

        ft = f.descToTS.get(timestamp_desc)
        if not ft:
            ft = set()
            f.descToTS[timestamp_desc] = ft

        ft.add(timestamp)
        return

    def run(self):
        """Entry point for the analyzer.

        Returns:
            String with summary of the analyzer result
        """
        query = ('(attribute_type:16 OR attribute_type:48)'
                 'AND NOT timestamp_desc:"Metadata Modification Time"'
                 'AND NOT timestamp_desc:"Content Modification Time"')

        return_fields = ['file_reference', 'timestamp', 'timestamp_desc',
                         'time_deltas', 'attribute_type', 'name']

        # Generator of events based on your query.
        events = self.event_stream(
            query_string=query, return_fields=return_fields)

        found = []
        file_names = dict()
        std_infos = dict()

        nameListMap = dict()

        for event in events:
            timestamp = event.source.get('timestamp')
            timestamp_desc = event.source.get('timestamp_desc')
            file_reference = event.source.get('file_reference')
            si_time_deltas = event.source.get('time_deltas')
            fn_time_delta = event.source.get('time_delta')
            attribute_type = event.source.get('attribute_type')
            name = event.source.get('name')

            if attribute_type == 16:
                self.insert(std_infos, file_reference, None, timestamp_desc,
                            int(timestamp / self.resolution),
                            si_time_deltas and max(si_time_deltas) > 0)

            if attribute_type == 48:
                self.insert(file_names, file_reference, name, timestamp_desc,
                            int(timestamp / self.resolution),
                            bool(fn_time_delta))

        for ref, f in file_names.items():
            if len(f.descToTS) == 2:
                for ct in f.descToTS[self.CDESC]:
                    for at in f.descToTS[self.ADESC]:
                        nameList = nameListMap.get(str(ct) + str(at))
                        if not nameList:
                            nameList = []
                            nameListMap[str(ct) + str(at)] = nameList
                        nameList.append(f.name)

        for ref, f in std_infos.items():
            if f.dirty and len(f.descToTS) == 2:
                for ct in f.descToTS[self.CDESC]:
                    for at in f.descToTS[self.ADESC]:
                        matches = nameListMap.get(str(ct) + str(at))
                        if matches:
                            found.append(file_names[ref].name + " "
                                         + str(matches) + "&")

        print(found)
        return 'bad files found: {0:d}'.format(len(found))



manager.AnalysisManager.register_analyzer(TestanaSketchPlugin)
