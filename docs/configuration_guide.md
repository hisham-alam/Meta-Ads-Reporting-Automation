# Ad Analysis Tool Configuration Guide

This document explains how to configure the Ad Analysis Tool to meet your specific requirements.

## Configuration File

The tool uses a JSON configuration file located at `config/analysis_config.json`. This file controls the core behavior of the tool, including ad selection criteria and account filtering.

### Example Configuration

```json
{
    "ad_selection_criteria": {
        "days_since_launch": 7,
        "minimum_spend": 250.0
    },
    "account_filters": {
        "enabled_accounts": ["GBR", "NAM"],
        "specific_adset_ids": [],
        "specific_campaign_ids": []
    }
}
```

## Configuration Options

### Ad Selection Criteria

These settings determine which ads are eligible for analysis:

- **days_since_launch**: The minimum number of days since an ad was launched before it's eligible for analysis. Default is 7 days.
- **minimum_spend**: The minimum amount of spend (in account currency) required for an ad to be analyzed. Default is 250.0.

**IMPORTANT**: Both criteria must be met for an ad to be eligible. The tool will only analyze ads that have been active for at least the specified number of days AND have spent at least the minimum amount.

### Account Filters

These settings control which accounts, campaigns, and adsets are analyzed:

- **enabled_accounts**: An array of account codes to analyze. Only accounts in this list will be processed. Account codes must match those in your `.env` file (e.g., "GBR", "EUR", "NAM", etc.).
- **specific_adset_ids**: An optional array of adset IDs to analyze. If this array is empty, all adsets in the enabled accounts will be analyzed (subject to campaign filtering). If specific IDs are provided, only ads within those adsets will be analyzed.
- **specific_campaign_ids**: An optional array of campaign IDs to analyze. If this array is empty, all campaigns in the enabled accounts will be analyzed (subject to adset filtering). If specific IDs are provided, only ads within those campaigns will be analyzed.

**Filter Logic**:

When using multiple filters, the following logic applies:

1. If only account filters are specified, all ads in those accounts are analyzed (subject to days and spend criteria).
2. If adset IDs are specified, only ads in those adsets are analyzed.
3. If campaign IDs are specified, only ads in those campaigns are analyzed.
4. If both adset IDs and campaign IDs are specified, ads that are either in the specified adsets OR in the specified campaigns will be analyzed. This means ads will be included even if the adset is in a different campaign than those specified.

## How Ad Selection Works

1. The tool first identifies all ads that were created at least `days_since_launch` days ago.
2. From those ads, it selects only those that have spent at least `minimum_spend`.
3. If `specific_adset_ids` are provided, it further filters to include only ads within those adsets.
4. Ads are sorted by spend amount (highest first) and limited to the maximum number specified when running the tool.

## Changing Configuration Values

To change the configuration:

1. Edit the `config/analysis_config.json` file with your desired settings.
2. Save the file.
3. Run the tool normally. It will automatically use the new settings.

The tool will respect the configuration settings as gospel and will not use any fallback methods if no ads meet the specified criteria.

## Running the Tool

Run the tool using:

```bash
python src/pipeline_manager.py --region GBR --max-ads 20
```

Where:
- `--region` specifies the region to analyze (must be in the `enabled_accounts` list)
- `--max-ads` sets the maximum number of ads to analyze (defaults to 20)

The tool will display the current configuration settings when it starts.