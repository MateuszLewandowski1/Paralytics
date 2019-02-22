import numpy as np 
import pandas as pd 

from inspect import currentframe, getargvalues
from sklearn.base import BaseEstimator, TransformerMixin
from pandas.api.types import is_numeric_dtype


class CategoricalGrouper(BaseEstimator, TransformerMixin):
    """Groups sparse observations in a categorical columns into one category.
    
    Parameters
    ----------
    method: string {'freq'} (default: 'freq')
        freq:
            Counts the frequency against each category. Retains categories
            whose cumulative share (with respect to descending sort) in the
            total dataset is equal or higher than the percentile threshold.
    
    percentile_thresh: float (default: .05)
        Defines the percentile threshold for 'freq' method.
    
    new_cat: string or int (default: 'Other')
        Specifies the category name that will be imputed to the chosen sparse
        observations.
    
    include_cols: list or None (default: None)
        Specifies column names that should be treated like categorical features.
        If None then estimator is executed only on the automatically selected
        categorical columns.
    
    exclude_cols: list or None (default: None)
        Specifies categorical column names that should not be treated like 
        categorical features. If None then no column is excluded from
        transformation.
    
    Attributes
    ----------
    cat_cols_: list
        List of categorical columns in a given dataset.
        
    imp_cats_: dict
        Dictionary that keeps track of replaced category names with the new
        category for every feature in the dataset.
    
    """
    def __init__(self, method='freq', percentile_thresh=.05, new_cat='Other', 
                 include_cols=None, exclude_cols=None):
        icf = currentframe()    
        args, _, _, values = getargvalues(icf)
        values.pop('self')

        for param, value in values.items():
            setattr(self, param, value)
    
    def fit(self, X, y=None):
        """Fits grouping with X by using given method.
        
        Parameters
        ----------
        X: DataFrame, shape (n_samples, n_features)
            Training data of independent variable values.
        
        y: ignore
        
        Returns
        -------
        self: object
            Returns the instance itself.
        
        """
        assert isinstance(X, pd.DataFrame), \
            'Input must be an instance of pandas.DataFrame()!'
        assert len(X) > 0, 'Input data can not be empty!'
        
        self.cat_cols_ = self._cat_cols_selection(
            X, self.include_cols, self.exclude_cols
        )
            
        self.imp_cats_ = {}
        if self.method == 'freq':
            for col in self.cat_cols_:
                tracker, i = 0, 0
                sorted_series = X[col].value_counts(normalize=True)
                while tracker < 1 - self.percentile_thresh:  
                    tracker += sorted_series.iloc[i]
                    i += 1
                sparse_cats = sorted_series.index[i:].tolist()
                if len(sparse_cats) > 1:
                    self.imp_cats_[col] = sparse_cats
                else:
                    self.imp_cats_[col] = []
        
        return self
        
    def transform(self, X):
        """Apply grouping of sparse categories on X.
        
        Parameters
        ----------
        X: DataFrame, shape (n_samples, n_features)
            Data with n_samples as its number of samples.
        
        Returns
        -------
        X_new: DataFrame, shape (n_samples_new, n_features)
            X data with substituted sparse categories to new_cat. 
        
        """
        try:
            getattr(self, 'imp_cats_')
            getattr(self, 'cat_cols_')
        except AttributeError:
            raise RuntimeError('Could not find the attribute.\n'
                               'Fitting is necessary before you do '
                               'the transformation.')
        assert isinstance(X, pd.DataFrame), \
            'Input must be an instance of pandas.DataFrame()'
        
        X_new = X.copy()
        for col in self.cat_cols_:
            row_indices = X_new[col].isin(self.imp_cats_[col])
            if X_new[col].dtype.name == 'category':
                try:
                    X_new[col].cat.add_categories(self.new_cat, inplace=True)
                except ValueError as e:
                    raise ValueError(
                        'You need to specify different "new_cat" value, '
                        'because the current one is already included in the '
                        'category names.'
                    ).with_traceback(e.__traceback__)
                cat_removals = list(
                    set(self.imp_cats_[col]).intersection(
                        X_new[col].cat.categories
                    )
                )
                X_new[col].cat.remove_categories(
                    cat_removals, 
                    inplace=True
                )
            X_new.loc[row_indices, col] = self.new_cat
        
        return X_new
    
    @staticmethod
    def _cat_cols_selection(X, include, exclude):
        """Returns categorical columns including the user's corrections.
        
        """
        cat_cols = X.select_dtypes('category').columns.tolist()

        if include is not None:
            assert isinstance(include, list), \
                'Columns to include must be given as an instance of a list!'
            cat_cols = [col for col in X.columns if col in cat_cols
                                                 or col in include]
                                                 
        if exclude is not None:
            assert isinstance(exclude, list), \
                'Columns to exclude must be given as an instance of a list!'
            cat_cols = [col for col in cat_cols if col not in exclude]
        
        return cat_cols


class ColumnProjector(BaseEstimator, TransformerMixin):
    """Projects variable types onto basic dtypes.

    If not specified projects numeric features onto float, boolean onto bool and
    categorical onto 'category' dtypes.

    Parameters
    ---------- 
    manual_projection: dictionary
        Dictionary where keys are dtype names onto which specified columns 
        will be projected and values are lists containing names of variables to
        be projected onto given dtype.
            Example: 
                manual_projection={
                    float: ['foo', 'bar'],
                    'category': ['baz'],
                    int: ['qux'],
                    bool: ['quux']
                }

    num_to_float: boolean (default: True)
        Specifies whether numerical variables should be projected onto float
        (if True) or onto int (if False).

    """
    def __init__(self, manual_projection=None, num_to_float=True):
        self.manual_projection = manual_projection
        self.num_to_float = num_to_float

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """Apply variable projection on X.

        Parameters
        ----------
        X: DataFrame, shape (n_samples, n_features)
            New data with n_samples as its number of samples.

        Returns
        -------
        X_new: DataFrame, shape (n_samples, n_features)
            X data with projected values onto specified dtype.

        """
        assert isinstance(X, pd.DataFrame), \
            'Input must be an instance of pandas.DataFrame()'

        X_new = X.copy()
        columns = X_new.columns
        if self.manual_projection is not None:
            assert isinstance(self.manual_projection, dict), \
                'manual_projection must be an instance of the dictionary!'
            for col_type, col_names in self.manual_projection.items():
                assert isinstance(col_names, list), (
                    'Values of manual_projection must be an instance ' 
                    'of the list!'
                )
                try:
                    X_new[col_names] = X_new[col_names].astype(col_type)
                    columns = [col for col in columns 
                               if col not in col_names]
                except KeyError:
                    cols_error = list(set(col_names) - set(X_new.columns))
                    raise KeyError("C'mon, those columns ain't in "
                                   "the DataFrame: %s" % cols_error)

        for col in columns:
            if set(X_new[col]) <= {0, 1}:
                X_new[col] = X_new[col].astype(bool)
            elif self.num_to_float and is_numeric_dtype(X_new[col]):
                X_new[col] = X_new[col].astype(float)
            elif is_numeric_dtype(X_new[col]):
                X_new[col] = X_new[col].astype(int)
            else:
                X_new[col] = X_new[col].astype('category')

        return X_new


class ColumnSelector(BaseEstimator, TransformerMixin):
    """
    Taken from:
    https://ramhiser.com/post/2018-04-16-building-scikit-learn-pipeline-
    with-pandas-dataframe/

    """
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """

        """
        assert isinstance(X, pd.DataFrame), \
            'Input must be an instance of pandas.DataFrame()'

        try:
            return X[self.columns]
        except KeyError:
            cols_error = list(set(self.columns) - set(X.columns))
            raise KeyError("C'mon, those columns ain't in the DataFrame: %s" 
                           % cols_error)


class TypeSelector(BaseEstimator, TransformerMixin):
    """
    Taken from:
    https://ramhiser.com/post/2018-04-16-building-scikit-learn-pipeline-
    with-pandas-dataframe/
    
    """
    def __init__(self, col_type):
        self.col_type = col_type

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """

        """
        assert isinstance(X, pd.DataFrame), \
            'Input must be an instance of pandas.DataFrame()'

        return X.select_dtypes(include=[self.col_type])