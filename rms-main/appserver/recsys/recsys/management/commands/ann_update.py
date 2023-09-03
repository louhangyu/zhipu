import json

from django.core.management.base import CommandParser

from recsys.ann import PaperIndex, PaperVectorIndex, PaperGPTVectorIndex
from recsys.algorithms.aggregate import Aggregate
from recsys.error_report_command import ErrorReportingCommand


class Command(ErrorReportingCommand):
    help = "ANN index update"

    def add_arguments(self, parser:CommandParser):
        """
        :param parser:
        :return:
        """
        parser.add_argument('--mode',
                            type=str,
                            required=False,
                            default="train",
                            help="You can select train | predict | rebuild | create | search. Default is train")
        parser.add_argument('--type',
                            type=str,
                            required=False,
                            default="pub",
                            help="You can select pub|pub_vector|pub_gpt")
        parser.add_argument('--query',
                            type=str,
                            required=False,
                            default=None,
                            help="")
        parser.add_argument('--query-file',
                            type=str,
                            required=False,
                            default=None,
                            help="Query file")
        parser.add_argument('--k',
                            type=int,
                            required=False,
                            default=10,
                            help="Max returns when query")

    def handle(self, *args, **options):
        index_type = options['type']
        if index_type == "pub":
            indexer = PaperIndex(timeout=30, prev_days=365*10)
        elif index_type == "pub_vector":
            indexer = PaperVectorIndex(prev_days=365*10)
        elif index_type == "pub_gpt":
            indexer = PaperGPTVectorIndex(prev_days=365*10)
        else:
            raise ValueError(f"unknown type {index_type}")

        if options['mode'] == "train":
            indexer.train()
        elif options['mode'] == "rebuild":
            indexer.rebuild()
        elif options['mode'] == 'create':
            indexer.create()
        elif options['mode'] == "search":
            if options['query']:
                papers = [{'title': options['query']}]
            elif options['query_file']:
                papers = []
                with open(options['query_file']) as f:
                    for line in f:
                        papers.append({'title': line.strip()})
            else:
                raise ValueError("Query is empty")
            
            for paper in papers:
                k = options['k']
                self.stdout.write(self.style.SUCCESS(f"{paper}, k {k}: "))
                neighbours = indexer.search_by_dict(paper, k=k, debug=False)
                agg = Aggregate()
                for i, neighbour in enumerate(neighbours):
                    pub = agg.preload_pub(neighbour[0])
                    if not pub:
                        self.stdout.write(f"\t{i}, {neighbour[0]} -> {neighbour[1]}")
                    else:
                        self.stdout.write(f"\t{i}, {pub['title']} -> {neighbour[1]}")
        else:
            raise ValueError(f"unknown mode {options['mode']}")
