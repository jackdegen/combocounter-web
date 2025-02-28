from abc import ABC, abstractmethod
import pandas as pd
import io
from typing import Dict, List, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field as PydanticField, validator


class PlayerPerformance(BaseModel):
    """Schema for player performance data"""
    name: str
    ownership: float = PydanticField(alias="own")
    fantasy_points: float = PydanticField(alias="fpts")

    class Config:
        allow_population_by_field_name = True


class ContestEntry(BaseModel):
    """Schema for individual contest entry"""
    rank: int
    entry_name: str = PydanticField(alias="entry")
    fantasy_points: float = PydanticField(alias="fpts")
    lineup: Tuple[str, ...]
    ordered_lineup: Optional[Tuple[str, ...]] = PydanticField(alias="ordered")

    class Config:
        allow_population_by_field_name = True


class FieldBase(ABC):
    """
    Abstract base class for analyzing DFS contest field data.
    Uses Pydantic for data validation and schema definition.
    """
    
    def __init__(self, file_buffer: Any) -> None:
        """
        Initialize Field object with raw data from file buffer.
        
        Args:
            file_buffer: File-like object containing contest data
        """
        self.raw = self._read_raw_data(file_buffer)
        self._clean_df: Optional[pd.DataFrame] = None
        self._performances_df: Optional[pd.DataFrame] = None
        self._entries: List[ContestEntry] = []
        self._player_performances: Dict[str, PlayerPerformance] = {}

    @abstractmethod
    def _read_raw_data(self, file_buffer: Any) -> pd.DataFrame:
        """
        Read and perform initial processing of raw data.
        Must be implemented by each sport-specific class.
        """
        pass

    @abstractmethod
    def clean_data(self, **kwargs) -> None:
        """
        Clean raw data into standardized format.
        Must be implemented by each sport-specific class.
        """
        pass

    @property
    def clean(self) -> pd.DataFrame:
        """
        Get cleaned data, processing it first if necessary.
        
        Returns:
            pd.DataFrame: Cleaned contest data
        """
        if self._clean_df is None:
            self.clean_data()
        return self._clean_df

    @property
    def performances(self) -> pd.DataFrame:
        """
        Get performance data, processing it first if necessary.
        
        Returns:
            pd.DataFrame: Player performance data
        """
        if self._performances_df is None:
            self.clean_data()
        return self._performances_df

    def ownership(self, **kwargs) -> Dict[str, float]:
        """
        Calculate ownership percentages for all players.
        
        Returns:
            Dict[str, float]: Mapping of player names to ownership percentages
        """
        if not self._player_performances:
            self.clean_data()
        return {
            name: player.ownership 
            for name, player in self._player_performances.items()
        }
    
    def get_contestant_entries(self, contestant: str) -> List[ContestEntry]:
        """
        Get all entries for a specific contestant.
        
        Args:
            contestant: Name of the contestant
            
        Returns:
            List[ContestEntry]: All entries submitted by the contestant
        """
        if not self._entries:
            self.clean_data()
        return [entry for entry in self._entries if entry.entry_name == contestant]


class PGAField(FieldBase):
    """Field analysis for PGA contests"""
    
    COLUMNS = {
        'raw': ['Player', '%Drafted', 'FPTS', 'Rank', 'EntryName', 'Points', 'Lineup'],
        'drop': ['Unnamed: 6', 'Roster Position'],
        'performances': ['Player', '%Drafted', 'FPTS'],
        'clean': ['Rank', 'EntryName', 'Points', 'Lineup']
    }

    def _read_raw_data(self, file_buffer: Any) -> pd.DataFrame:
        """
        Read PGA-specific contest data format.
        """
        return (pd
                .read_csv(file_buffer, dtype='str')
                .drop(self.COLUMNS['drop'], axis=1, errors='ignore')
               )

    @staticmethod
    def _convert_to_lineup(lineup_str: str) -> Tuple[str, ...]:
        """
        Convert PGA lineup string to tuple of player names.
        """
        parts = [part for part in lineup_str.split('G ') if len(part)]
        return tuple(part.strip() for part in parts)

    def clean_data(self, **kwargs) -> None:
        """
        Process raw PGA data into standardized format.
        Creates both performance and lineup DataFrames.
        """
        if self._clean_df is not None:
            return
        
        # Process performances
        self._performances_df = (self.raw
                          .copy(deep=True)
                          [['Player', '%Drafted', 'FPTS']]
                          .rename(columns={'Player': 'name', '%Drafted': 'own', 'FPTS': 'fpts'})
                          .dropna()
                          .assign(
                              own=lambda df_: df_.own.map(lambda x: float(x.replace('%', ''))),
                              fpts=lambda df_: df_.fpts.astype('float')
                          )
                          .set_index('name')
                         )
        
        # Store as Pydantic models
        for name, row in self._performances_df.reset_index().iterrows():
            player = PlayerPerformance(**row.to_dict())
            self._player_performances[player.name] = player
        
        # Process entries
        self._clean_df = (self.raw
                    .copy(deep=True)
                    [['Rank', 'EntryName', 'Points', 'Lineup']]
                    .rename(columns={'Rank': 'rank', 'EntryName': 'entry', 'Points': 'fpts', 'Lineup': 'lineup'})
                    .dropna()
                    .assign(
                        rank=lambda df_: df_.rank.astype(int),
                        fpts=lambda df_: df_.fpts.astype(float),
                        lineup=lambda df_: df_.lineup.map(self._convert_to_lineup),
                        entry=lambda df_: df_.entry.map(lambda x: x.split(' ')[0]),
                        ordered=lambda df_: df_.lineup.map(lambda x: tuple(sorted(x)))
                    )
                   )
        
        # Store as Pydantic models
        self._entries = [ContestEntry(**row.to_dict()) for _, row in self._clean_df.iterrows()]


class NFLField(FieldBase):
    """Field analysis for NFL contests"""
    
    COLUMNS = {
        'raw': ['Player', '%Drafted', 'FPTS', 'Rank', 'EntryName', 'Points', 'Lineup'],
        'drop': ['Unnamed: 6', 'Roster Position'],
        'performances': ['Player', '%Drafted', 'FPTS'],
        'clean': ['Rank', 'EntryName', 'Points', 'Lineup']
    }

    def _read_raw_data(self, file_buffer: Any) -> pd.DataFrame:
        """
        Read NFL-specific contest data format.
        """
        return (pd
                .read_csv(file_buffer, dtype='str')
                .drop(self.COLUMNS['drop'], axis=1, errors='ignore')
               )

    @staticmethod
    def _convert_to_lineup(lineup_str: str) -> Tuple[str, ...]:
        """
        Convert NFL lineup string to tuple of player names.
        """
        # NFL-specific lineup parsing logic
        parts = []
        for position in ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST']:
            parts.extend([part.strip() for part in lineup_str.split(f'{position} ') if len(part)])
        return tuple(parts)

    def clean_data(self, **kwargs) -> None:
        """
        Process raw NFL data into standardized format.
        """
        # NFL-specific data cleaning logic, similar to PGA but with NFL-specific parsing
        # ...


class NBAField(FieldBase):
    """Field analysis for NBA contests"""
    
    COLUMNS = {
        'raw': ['Player', '%Drafted', 'FPTS', 'Rank', 'EntryName', 'Points', 'Lineup'],
        'drop': ['Unnamed: 6', 'Roster Position'],
        'performances': ['Player', '%Drafted', 'FPTS'],
        'clean': ['Rank', 'EntryName', 'Points', 'Lineup']
    }

    def _read_raw_data(self, file_buffer: Any) -> pd.DataFrame:
        """
        Read NBA-specific contest data format.
        """
        return (pd
                .read_csv(file_buffer, dtype='str')
                .drop(self.COLUMNS['drop'], axis=1, errors='ignore')
               )

    @staticmethod
    def _convert_to_lineup(lineup_str: str) -> Tuple[str, ...]:
        """
        Convert NBA lineup string to tuple of player names.
        """
        # NBA-specific lineup parsing logic
        parts = []
        for position in ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']:
            parts.extend([part.strip() for part in lineup_str.split(f'{position} ') if len(part)])
        return tuple(parts)

    def clean_data(self, **kwargs) -> None:
        """
        Process raw NBA data into standardized format.
        """
        # NBA-specific data cleaning logic, similar to PGA but with NBA-specific parsing
        # ...


def create_field(sport: str, file_buffer: Any, mode: str = 'classic') -> FieldBase:
    """
    Factory function to create appropriate Field object based on sport.
    
    Args:
        sport: Sport identifier ('PGA', 'NFL', 'NBA')
        file_buffer: File-like object containing contest data
        mode: Game mode ('classic' or 'showdown')
        
    Returns:
        FieldBase: Appropriate Field subclass instance
        
    Raises:
        ValueError: If sport is not supported
    """
    field_classes = {
        'PGA': PGAField,
        'NFL': NFLField,
        'NBA': NBAField
    }
    
    if sport.upper() not in field_classes:
        raise ValueError(f"Unsupported sport: {sport}. Must be one of {list(field_classes.keys())}")
    
    return field_classes[sport.upper()](file_buffer)