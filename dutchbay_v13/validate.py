#!/usr/bin/env python3
"""
Parameter Validation Module for Dutch Bay Financial Model
Provides comprehensive input validation with clear error messages
"""
from typing import Dict, Any, List, Tuple
import warnings


class ValidationError(Exception):
    """Custom exception for parameter validation failures."""
    pass


def validate_project_parameters(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate all project parameters against reasonable bounds.
    
    Args:
        params: Dictionary of project parameters
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # CAPEX validation
    if 'total_capex' in params or 'CAPEX_TOTAL' in params:
        capex = params.get('total_capex', params.get('CAPEX_TOTAL'))
        if not (10 < capex < 500):
            errors.append(f"CAPEX {capex}M USD is outside reasonable range (10-500M USD)")
    
    # Capacity factor validation
    if 'cf_p50' in params or 'CF_P50' in params:
        cf = params.get('cf_p50', params.get('CF_P50'))
        if not (0.15 < cf < 0.65):
            errors.append(f"Capacity factor {cf:.1%} is outside reasonable range (15%-65%)")
    
    # Nameplate capacity validation
    if 'nameplate_mw' in params or 'NAMEPLATE_MW' in params:
        mw = params.get('nameplate_mw', params.get('NAMEPLATE_MW'))
        if not (10 < mw < 500):
            errors.append(f"Nameplate capacity {mw}MW is outside reasonable range (10-500MW)")
    
    # Degradation validation
    if 'yearly_degradation' in params or 'YEARLY_DEGRADATION' in params:
        deg = params.get('yearly_degradation', params.get('YEARLY_DEGRADATION'))
        if not (0 < deg < 0.02):
            errors.append(f"Degradation {deg:.2%}/year is outside reasonable range (0%-2%/year)")
    
    # Tax rate validation
    if 'tax_rate' in params or 'TAX_RATE' in params:
        tax = params.get('tax_rate', params.get('TAX_RATE'))
        if not (0 <= tax < 0.60):
            errors.append(f"Tax rate {tax:.1%} is outside reasonable range (0%-60%)")
    
    # FX depreciation validation
    if 'fx_depr' in params or 'FX_DEPR' in params:
        fx_depr = params.get('fx_depr', params.get('FX_DEPR'))
        if not (-0.10 < fx_depr < 0.20):
            errors.append(f"FX depreciation {fx_depr:.1%}/year is outside reasonable range (-10% to +20%/year)")
    
    # Initial FX rate validation
    if 'fx_initial' in params or 'FX_INITIAL' in params:
        fx_init = params.get('fx_initial', params.get('FX_INITIAL'))
        if not (100 < fx_init < 500):
            errors.append(f"Initial FX rate {fx_init} LKR/USD is outside reasonable range (100-500)")
    
    # Interest rate validation
    if 'usd_debt_rate' in params or 'USD_DEBT_RATE' in params:
        usd_rate = params.get('usd_debt_rate', params.get('USD_DEBT_RATE'))
        if not (0.01 < usd_rate < 0.20):
            errors.append(f"USD interest rate {usd_rate:.1%} is outside reasonable range (1%-20%)")
    
    if 'lkr_debt_rate' in params or 'LKR_DEBT_RATE' in params:
        lkr_rate = params.get('lkr_debt_rate', params.get('LKR_DEBT_RATE'))
        if not (0.01 < lkr_rate < 0.25):
            errors.append(f"LKR interest rate {lkr_rate:.1%} is outside reasonable range (1%-25%)")
    
    # Project life validation
    if 'project_life_years' in params or 'PROJECT_YEARS' in params:
        years = params.get('project_life_years', params.get('PROJECT_YEARS'))
        if not (10 <= years <= 30):
            errors.append(f"Project life {years} years is outside reasonable range (10-30 years)")
    
    # OPEX validation
    if 'opex_usd_mwh' in params or 'OPEX_USD_MWH' in params:
        opex = params.get('opex_usd_mwh', params.get('OPEX_USD_MWH'))
        if not (2 < opex < 20):
            errors.append(f"OPEX {opex} USD/MWh is outside reasonable range (2-20 USD/MWh)")
    
    # Tariff validation
    if 'tariff_lkr_kwh' in params or 'TARIFF_LKR_KWH' in params:
        tariff = params.get('tariff_lkr_kwh', params.get('TARIFF_LKR_KWH'))
        if not (5 < tariff < 50):
            errors.append(f"Tariff {tariff} LKR/kWh is outside reasonable range (5-50 LKR/kWh)")
    
    # SSCL rate validation
    if 'sscl_rate' in params or 'SSCL_RATE' in params:
        sscl = params.get('sscl_rate', params.get('SSCL_RATE'))
        if not (0 <= sscl < 0.10):
            errors.append(f"SSCL rate {sscl:.1%} is outside reasonable range (0%-10%)")
    
    # Debt tenure validation
    if 'usd_debt_tenor' in params or 'USD_DEBT_TENOR' in params:
        tenor = params.get('usd_debt_tenor', params.get('USD_DEBT_TENOR'))
        if not (5 <= tenor <= 20):
            errors.append(f"USD debt tenor {tenor} years is outside reasonable range (5-20 years)")
    
    # OPEX split validation
    if 'opex_split_usd' in params and 'opex_split_lkr' in params:
        usd_split = params['opex_split_usd']
        lkr_split = params['opex_split_lkr']
        if abs((usd_split + lkr_split) - 1.0) > 0.01:
            errors.append(f"OPEX splits don't sum to 1.0: USD {usd_split} + LKR {lkr_split} = {usd_split+lkr_split}")
    
    return (len(errors) == 0, errors)


def validate_debt_structure(debt: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate debt structure parameters.
    
    Args:
        debt: Dictionary of debt parameters
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Total debt validation
    if 'total_debt' in debt:
        total = debt['total_debt']
        if total < 0:
            errors.append("Total debt cannot be negative")
        if total > 500:
            errors.append(f"Total debt {total}M USD seems unreasonably high (>500M)")
    
    # USD/LKR debt split validation
    if 'usd_debt' in debt and 'lkr_debt' in debt and 'total_debt' in debt:
        usd = debt['usd_debt']
        lkr = debt['lkr_debt']
        total = debt['total_debt']
        
        if abs((usd + lkr) - total) > 0.01:
            errors.append(f"USD debt ({usd}) + LKR debt ({lkr}) != Total debt ({total})")
    
    # DFI percentage validation
    if 'dfi_pct_of_usd' in debt:
        dfi_pct = debt['dfi_pct_of_usd']
        if not (0 <= dfi_pct <= 0.30):
            errors.append(f"DFI percentage {dfi_pct:.1%} is outside reasonable range (0%-30%)")
    
    return (len(errors) == 0, errors)


def validate_and_warn(params: Dict[str, Any], debt: Dict[str, Any] = None) -> None:
    """
    Validate parameters and issue warnings for any violations.
    Raises ValidationError if critical violations found.
    
    Args:
        params: Project parameters dictionary
        debt: Optional debt structure dictionary
    """
    # Validate project parameters
    is_valid, errors = validate_project_parameters(params)
    
    if not is_valid:
        error_msg = "Parameter validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        if len(errors) > 3:  # Too many errors = critical failure
            raise ValidationError(error_msg)
        else:  # Few errors = warnings only
            warnings.warn(error_msg)
    
    # Validate debt structure if provided
    if debt is not None:
        is_valid, errors = validate_debt_structure(debt)
        if not is_valid:
            error_msg = "Debt structure validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            if len(errors) > 2:
                raise ValidationError(error_msg)
            else:
                warnings.warn(error_msg)


def validate_scenario_matrix(scenarios: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a batch of scenarios from scenario matrix.
    
    Args:
        scenarios: List of parameter dictionaries
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    all_errors = []
    
    for i, scenario in enumerate(scenarios):
        is_valid, errors = validate_project_parameters(scenario)
        if not is_valid:
            all_errors.append(f"Scenario {i+1}: " + "; ".join(errors))
    
    return (len(all_errors) == 0, all_errors)


if __name__ == "__main__":
    # Example usage
    test_params = {
        'total_capex': 155.0,
        'cf_p50': 0.40,
        'nameplate_mw': 150,
        'yearly_degradation': 0.006,
        'tax_rate': 0.30,
        'fx_depr': 0.03,
        'fx_initial': 300,
        'usd_debt_rate': 0.07,
        'project_life_years': 20,
        'opex_usd_mwh': 6.83,
        'tariff_lkr_kwh': 20.36
    }
    
    is_valid, errors = validate_project_parameters(test_params)
    if is_valid:
        print("✓ All parameters valid")
    else:
        print("✗ Validation errors:")
        for error in errors:
            print(f"  - {error}")
