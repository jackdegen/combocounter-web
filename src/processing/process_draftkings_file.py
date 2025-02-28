import pandas as pd

from __info import PLAYER_COLUMNS

class ProcessDraftKingsFile:

    @staticmethod
    def extract_player_data_from_dk_file(path) -> pd.DataFrame:
        """
        Extracts the player data that is provided with upload templates
            Position   Name + ID   Name   ID   Roster Position   Salary   Game Info
        """
        df = pd.read_csv(path, skiprows=7)
        columns = list(df.columns)[11:16]

        # Keeping position in just in case data is useful later
        return (df
                .loc[:, columns]
                .dropna()
                .pipe(lambda df_: df_.loc[df_['Roster Position'] != 'CPT'])
                .assign(ID=lambda df_: df_.ID.astype('int'))
                .drop(['Name + ID', 'Roster Position'], axis=1)
                .reset_index(drop=True)
                .set_axis(['pos', 'name', 'id'], axis=1)
               )

    @staticmethod
    def extract_lineups_from_dk_file(path: str, columns: list[str,...]) -> pd.DataFrame:
        """
        Extracts the lineups from DraftKings file
        Offsets by 4 since DK files first 4 are:
            Entry ID   Contest Name   Contest ID   Entry Fee
        """



        #Issue is here
        ret = (pd
                .read_csv(path, usecols=range(4, 4+len(columns)))
                .set_axis(columns, axis=1)
                .dropna()
                # # Replace IDs
                .replace(r'\s*\(\d+\)', '', regex=True)
               )

        return ret

    def __init__(
            self,
            path: str,
            sport: str,
            mode: str,
            is_dk_file: bool
        ):

        # Path is actually type <tempfile.SpooledTemporaryFile> not a str or <os.path>
        # Because it is a filestream, it can only be used in a pd.read_csv() once before becoming unavailble.
        # Therefore, a bool was created that the user has to check on the webpage

        self.path = path

        self.columns = PLAYER_COLUMNS[sport][mode]
        self.is_dk_file = is_dk_file

        if self.is_dk_file:
            self.lineups = self.extract_lineups_from_dk_file(self.path, self.columns)
        
        else:
            self.lineups = (pd
                           .read_csv(self.path, usecols=range(len(self.columns)))
                           .set_axis(self.columns, axis=1)
                           )

        
