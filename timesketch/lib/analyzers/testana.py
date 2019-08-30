"""Sketch analyzer plugin for testana."""
from __future__ import unicode_literals

from timesketch.lib.analyzers import interface
from timesketch.lib.analyzers import manager

class Info(object):
    def __init__(self):
        self.desc_to_ts = dict()
        self.desc_to_event = dict()
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

    def insert(self, m, event, file_ref, name, timestamp_desc, timestamp, is_dirty):
        """return if file is dirty, number of types of timestamps"""
        f = m.get(file_ref)
        if not f:
            f = Info()
            m[file_ref] = f
        f.dirty = f.dirty or is_dirty
        f.name = name

        f_timestamps = f.desc_to_ts.get(timestamp_desc)
        if not f_timestamps:
            f_timestamps = set()
            f.desc_to_ts[timestamp_desc] = f_timestamps

        f_timestamps.add(timestamp)

        f_events = f.desc_to_event.get(timestamp_desc)
        if not f_events:
            f_events = set()
            f.desc_to_event[timestamp_desc] = f_events

        f_events.add(event)

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

        file_names = dict()
        std_infos = dict()

        matchListMap = dict()

        for event in events:
            timestamp = event.source.get('timestamp')
            timestamp_desc = event.source.get('timestamp_desc')
            file_reference = event.source.get('file_reference')
            si_time_deltas = event.source.get('time_deltas')
            fn_time_delta = event.source.get('time_delta')
            attribute_type = event.source.get('attribute_type')
            name = event.source.get('name')

            if attribute_type == 16:
                self.insert(std_infos, event, file_reference, None, timestamp_desc,
                            int(timestamp / self.resolution),
                            si_time_deltas and max(si_time_deltas) > 0)

            if attribute_type == 48:
                self.insert(file_names, event, file_reference, name, timestamp_desc,
                            int(timestamp / self.resolution),
                            bool(fn_time_delta))

        # TODO: Choose what events we want to flag.
        # TODO: Choose format of attribute.
        for ref, f in file_names.items():
            if len(f.desc_to_ts) == 2:
                for ct in f.desc_to_ts[self.CDESC]:
                    for at in f.desc_to_ts[self.ADESC]:
                        matchList = matchListMap.get(str(ct) + str(at))
                        if not matchList:
                            matchList = []
                            matchListMap[str(ct) + str(at)] = matchList
                        matchList.append(str(ref) + "-" + f.name)

        found = 0
        for ref, f in std_infos.items():
            if not f.dirty or not len(f.desc_to_ts) == 2:
                continue

            for ct in f.desc_to_ts[self.CDESC]:
                for at in f.desc_to_ts[self.ADESC]:
                    matchList = matchListMap.get(str(ct) + str(at))
                    if matchList:
                        found = found + 1
                        for event_set in f.desc_to_event.values():
                            for event in event_set:
                                event.add_attributes({'time_match': matchList})
                                event.commit()


        if found:
            self.sketch.add_view(
                view_name="Timestomp_Match", analyzer_name=self.NAME,
                query_string='_exists_:timestomp_matches')
        return 'bad files found: {0:d}'.format(found)



manager.AnalysisManager.register_analyzer(TestanaSketchPlugin)
