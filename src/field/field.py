import pandas as pd


def flatten(nested_seq):
        """
        Takes 2d sequence and returns all values in 1d
        Example: [(a,b,c), (a,y,z), (a,b,z)] -> [a, b, c, a, y, z, a, b, z]
        TODO: kwargs to add functionality
            - unique: [(a,b,c), (a,y,z), (a,b,z)] -> [a, b, c, y, z]
            - counts dictionary: [(a,b,c), (a,y,z), (a,b,z)] -> {a: 3, b: 2, z: 2, c: 1, z: 1} # TODO
            - etc
        """
        # if kwargs.get('unique', False):
        #     return set(flatten(nested_seq))

        return [element for inner_seq in nested_seq for element in inner_seq]
        # return list(itertools.chain.from_iterable(nested_seq))

class Field:

    def __init__(self, file_buffer, **kwargs):

        self.sport = kwargs.get('sport', 'PGA').upper()
        self.mode = kwargs.get('mode', 'classic').lower()

        self.raw = (pd
                    .read_csv(file_buffer, dtype='str')
                    .drop(['Unnamed: 6', 'Roster Position'], axis=1)
                   )

        if 'UTIL' in self.raw['Lineup'].iloc[0] and self.sport == 'PGA':
            self.sport='NBA'

    @staticmethod
    def convert_to_lineup_PGA(lineup_str: str) -> tuple[str,str,str,str,str,str]:
        """
        Removes the positions (' G ') from the provided string and then creates lineup with all positions removed.
        """
        parts = [part for part in lineup_str.split('G ') if len(part)]
        return tuple([part.strip() for part in parts])


    @staticmethod
    def convert_to_lineup_NBA(lineup_str: str) -> tuple[str,str,str,str,str,str]:
        """
        Removes the positions pos from the provided string and then creates lineup with all positions removed.
        EXAMPLE: C Alexandre Sarr F Paolo Banchero G Ryan Rollins PF Evan Mobley PG Cole Anthony SF Kyle Kuzma SG Donovan Mitchell UTIL Orlando Robinson
            - Since C always comes first (need to confirm), that will be special case after everything else.
            - Don't want to mess up data integrity accidently
            - Only way this causes issues if there is part of a name ending in uppercase --> "C" (for example, doing it this way if it had been "G" instead would cause issues with "OG Anunoby")
        """

        for pos_str in ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']:
            chars_with_padding = f' {pos_str} ' if pos_str != 'C' else 'C '
            lineup_str = lineup_str.replace(chars_with_padding, '_')

        parts = [part for part in lineup_str.split('_') if len(part)]
        return tuple([part.strip() for part in parts])

    def convert_to_lineup(self, lineup_str: str) -> tuple[str,str,str,str,str,str]:
        """
        Removes the positions (' G ') from the provided string and then creates lineup with all positions removed.
        """
        return {'NBA': self.convert_to_lineup_NBA, 'PGA': self.convert_to_lineup_PGA}[self.sport](lineup_str)

    @staticmethod
    def exposures(lineups: tuple[tuple[str,...], ...], **kwargs) -> pd.Series:
        """
        Returns the exposure of players in multiple lineups
        """

        n_lineups = len(lineups)
        flattened = flatten(lineups)
        n_players = len(set(flattened))

        # level = kwargs.get('level', 1)

        # Raw numbers
        # counts = {name_: flattened.count(name_) for name_ in set(flattened)}

        # Exposures as percentages
        exposure = {name_: 100 * flattened.count(name_) / n_lineups for name_ in set(flattened) if name_.strip() != 'LOCKED'}
        contestant = kwargs.get('contestant')

        title = 'Exposures'
        if contestant is not None:
            title += f" for {contestant}'s {n_lineups} entries, (N = {n_players}):"

        if kwargs.get('values', False):
            return pd.Series(exposure).sort_values(ascending=False)

        return (pd
                .Series(exposure)
                .sort_values()
                .plot
                .barh(
                    figsize=kwargs.get('figsize', (90,60)),
                    title=title
                )
               )

    def order_lineup(self, lineup_tup: tuple[str,...]) -> tuple[str,...]:
        """
        Accounting for CPT in showdown
        """
        return tuple(sorted(lineup_tup)) if self.mode == 'classic' else (lineup_tup[0],) + tuple(sorted(lineup_tup[1:]))

    def clean_data(self, **kwargs) -> None:
        """
        Cleans the raw DraftKings provided file into customized format.
        TODO: Documentation when functionality added
        """

        if hasattr(self, 'clean'):
            return

        print("Entering clean_data...")
        print(f"DataFrame columns: {self.raw.columns.tolist()}")

        self.performances = (self.raw
                             .copy(deep=True)
                             [['Player', '%Drafted', 'FPTS']]
                             .set_axis(['name', 'own', 'fpts'], axis=1)
                             .dropna()
                             .assign(
                                 own=lambda df_: df_.own.map(lambda ownstr: float(ownstr.replace('%', ''))),
                                 fpts=lambda df_: df_.fpts.astype('float')
                             )
                             .set_index('name')
                            )

        self.clean = (self.raw
                      .copy(deep=True)
                      [['Rank', 'EntryName', 'Points', 'Lineup']]
                      .set_axis(['rank', 'entry', 'fpts', 'lineup'], axis=1)
                      .dropna()
                      .assign(
                          lineup=lambda df_: df_.lineup.map(lambda lineup_str_: self.convert_to_lineup(lineup_str_)),
                          # Remove the brackets showing which entry of persons
                          entry=lambda df_: df_.entry.map(lambda entry_str: entry_str.split(' ')[0]),
                          # Ordered lineup, no longer ordered by position
                          ordered=lambda df_: df_.lineup.map(lambda lineup_: self.order_lineup(lineup_))
                      )
                     )

        return

    def ownership(self, **kwargs):

        if not hasattr(self, 'clean'):
            self.clean_data()

        return {name: self.performances.loc[name, 'own'] for name in self.performances.index}

    def leverage(self, contestant: str) -> dict[str,float]:
        if not hasattr(self, 'clean'):
            self.clean_data()

        # contestant = kwargs.get('contestant', 'jdeegs99')
        entries = tuple(self.clean.loc[self.clean['entry'] == contestant, 'ordered'])

        if not len(entries):
            print(f'{contestant} did not compete in this contest.')
            return

        exposures = (pd
                     .DataFrame(self.exposures(entries, values=True))
                     .set_axis(['own'], axis=1)
                    )

        # if 'LOCKED' in exposures:
        #     self.performances.loc['LOCKED','own'] = 0.0

        for name in set(self.performances.index).difference(set(exposures.index)):
            exposures.loc[name, 'own'] = 0.0

        ownership = (self.performances
                        # .reset_index()
                    #  [['name', 'own']]
                    [['own']]
                    #  .set_index('name')
                    )

        # if kwargs.get('values', True):
        return (exposures
                .sub(ownership)
                .rename({'own': 'leverage'}, axis=1)
                .sort_values('leverage', ascending=False)
                )

        # return (exposures
        #         .sub(ownership)
        #         .rename({'own': 'leverage'}, axis=1)
        #         .sort_values('leverage')
        #         .plot
        #         .barh(
        #             figsize=kwargs.get('figsize', (21,14)),
        #             title=f'Leverage breakdown for {contestant}\'s {len(entries)} entries.'
        #         )
        #        )

    def max_entries(self) -> dict[str,int]:
        if not hasattr(self, 'clean'):
            self.clean_data()

         # Count entries per contestant
        entry_counts = self.clean['entry'].value_counts()

        # Find the maximum count
        max_count = entry_counts.max()

        # # Filter for contestants with max count
        # max_entries = {}
        # for contestant, count in entry_counts.items():
        #     if count == max_count:
        #         # Explicitly convert to str and int
        #         max_entries[str(contestant)] = int(count)

        # return max_entries

        return {
            entry: count
            for entry, count in entry_counts.items()
            if count == max_count
        }

    def duplicates(self, **kwargs):
        """
        Returns all lineups that were duped more than 5x (for now)
        """
        if not hasattr(self, 'clean'):
            self.clean_data()

        dupes = (self.clean
                 .groupby('ordered')
                 ['lineup']
                 .agg(['count'])
                 .pipe(lambda df_: df_.loc[df_['count'] > 5])
                 .sort_values('count', ascending=False)
                )

        return dupes


    def mme_ownership(self):
        if not hasattr(self, 'clean'):
            self.clean_data()

        return self.exposures(tuple(self.clean.loc[self.clean['entry'].isin(self.max_entries()), 'ordered']), values=True)