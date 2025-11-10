#!/usr/bin/env python3
"""
Monte Carlo Simulation module for Dutch Bay 150MW Wind Farm Financial Model V12
Generates scenario analysis by varying key parameters (debt, fx, CF, rates)
ENHANCED with type hints, parameter correlation, and validation
"""
from typing import Optional, Dict
import numpy as np
import pandas as pd

from .legacy_v12 import (
    create_default_parameters,
    create_default_debt_structure,
    build_financial_model,
    ProjectParameters,
    DebtStructure,
    FinancialResults,
    USD_MKT_RATE, USD_DFI_RATE, LKR_DEBT_RATE,
    MAX_DEBT_RATIO, USD_DEBT_RATIO, USD_DFI_PCT, DEBT_TENOR_YEARS
)

from parameter_validation import validate_project_parameters, validate_debt_structure
import warnings


def generate_mc_parameters(
    n_scenarios: int,
    seed: Optional[int] = None,
    correlation: bool = False
) -> Dict[str, np.ndarray]:
    """
    Generate Monte Carlo parameter samples.
    
    Args:
        n_scenarios: Number of scenarios to generate
        seed: Random seed for reproducibility
        correlation: Whether to apply correlation between USD and LKR rates
        
    Returns:
        Dictionary of parameter arrays
    """
    rng = np.random.default_rng(seed)
    
    if correlation:
        # Generate correlated USD and LKR rates
        mean = [0.075, 0.0825]  # USD, LKR means
        cov = [[0.0001, 0.00008],  # Correlation ~0.8
               [0.00008, 0.00015]]
        rates = rng.multivariate_normal(mean, cov, n_scenarios)
        usd_rate = np.clip(rates[:, 0], 0.065, 0.09)
        lkr_rate = np.clip(rates[:, 1], 0.075, 0.09)
    else:
        usd_rate = rng.uniform(0.065, 0.09, n_scenarios)
        lkr_rate = rng.uniform(0.075, 0.09, n_scenarios)
    
    return {
        'usd_rate': usd_rate,
        'lkr_rate': lkr_rate,
        'debt_ratio': rng.uniform(0.5, 0.8, n_scenarios),
        'fx_depr': rng.uniform(0.03, 0.05, n_scenarios),
        'capacity_factor': rng.uniform(0.38, 0.42, n_scenarios),
    }


def run_monte_carlo(
    iterations: int = 1000,
    seed: Optional[int] = None,
    correlation: bool = False,
    validate: bool = True
) -> pd.DataFrame:
    """
    Run Monte Carlo simulation with enhanced error handling.
    
    Args:
        iterations: Number of MC scenarios
        seed: Random seed for reproducibility  
        correlation: Apply parameter correlation
        validate: Validate parameters before running
        
    Returns:
        DataFrame of scenario results
    """
    params = create_default_parameters()
    debt_template = create_default_debt_structure()
    scenarios = generate_mc_parameters(iterations, seed, correlation)
    out_data = []
    
    failed_count = 0
    
    for i in range(iterations):
        try:
            capfac = scenarios['capacity_factor'][i]
            fxdepr = scenarios['fx_depr'][i]
            dratio = scenarios['debt_ratio'][i]
            urate = scenarios['usd_rate'][i]
            lrate = scenarios['lkr_rate'][i]

            p = ProjectParameters(
                **{**params.__dict__, 'cf_p50': capfac, 'fx_depr': fxdepr}
            )
            
            if validate:
                is_valid, errors = validate_project_parameters(p.__dict__)
                if not is_valid:
                    warnings.warn(f"Scenario {i+1} validation failed: {errors[0]}")
                    continue
            
            td = p.total_capex * dratio
            ud = td * 0.45
            ld = td - ud
            debt = DebtStructure(
                **{**debt_template.__dict__,
                   'total_debt': td,
                   'usd_debt': ud,
                   'lkr_debt': ld,
                   'usd_mkt_rate': urate,
                   'lkr_rate': lrate}
            )
            
            results = build_financial_model(p, debt)
            
            out_data.append({
                'iteration': i+1,
                'usd_rate': urate,
                'lkr_rate': lrate,
                'debt_ratio': dratio,
                'fx_depr': fxdepr,
                'capacity_factor': capfac,
                'equity_irr': results['equity_irr'],
'project_irr': results['project_irr'],
'npv_12pct': results['npv_12pct'],
'min_dscr': results['min_dscr']
            })
        except Exception as e:
            failed_count += 1
            warnings.warn(f"Scenario {i+1} failed: {str(e)}")
            continue
    
    if failed_count > 0:
        warnings.warn(f"Monte Carlo: {failed_count}/{iterations} scenarios failed")
    
    df = pd.DataFrame(out_data)
    
    # Add summary statistics as attributes
    if len(df) > 0:
        df.attrs['mean_equity_irr'] = df['equity_irr'].mean()
        df.attrs['p10_equity_irr'] = df['equity_irr'].quantile(0.10)
        df.attrs['p90_equity_irr'] = df['equity_irr'].quantile(0.90)
        df.attrs['success_rate'] = len(df) / iterations
    
    return df
